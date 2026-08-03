import base64
import hashlib
import hmac
import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Dict, List
from urllib.parse import unquote, urlparse
from urllib import error, request


LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "")
PORT = int(os.getenv("PORT", "8000"))
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
WEBHOOK_PATH = "/callback"
SKIP_LINE_SIGNATURE_VALIDATION = (
    os.getenv("SKIP_LINE_SIGNATURE_VALIDATION", "false").strip().lower() == "true"
)


QUESTIONS: List[Dict] = [
    {
        "id": "q1",
        "text": "最近、疲れやすくて少し動いただけでも息が上がりやすいですか？",
        "weights": {"qi_deficiency": 2, "blood_deficiency": 1},
    },
    {
        "id": "q2",
        "text": "風邪をひきやすく、治るまで長引きやすいと感じますか？",
        "weights": {"qi_deficiency": 2},
    },
    {
        "id": "q3",
        "text": "ストレスがたまると、イライラしたりため息が増えたりしますか？",
        "weights": {"qi_stagnation": 2, "blood_stasis": 1},
    },
    {
        "id": "q4",
        "text": "脇腹が張る感じや、喉に何かつかえる感じはありますか？",
        "weights": {"qi_stagnation": 2, "water_toxicity": 1},
    },
    {
        "id": "q5",
        "text": "顔色が白っぽく見えたり、立ちくらみしやすかったりしますか？",
        "weights": {"blood_deficiency": 2},
    },
    {
        "id": "q6",
        "text": "爪が割れやすい・髪がパサつく・目が疲れやすい、に当てはまりますか？",
        "weights": {"blood_deficiency": 2, "yin_deficiency": 1},
    },
    {
        "id": "q7",
        "text": "肩こりが続きやすく、同じ場所がズキッと痛むことがありますか？",
        "weights": {"blood_stasis": 2},
    },
    {
        "id": "q8",
        "text": "顔色や唇の色がくすみやすく、冷えも気になりますか？",
        "weights": {"blood_stasis": 2, "water_toxicity": 1},
    },
    {
        "id": "q9",
        "text": "のぼせやすいのに、肌や喉の乾燥も気になりますか？",
        "weights": {"yin_deficiency": 2},
    },
    {
        "id": "q10",
        "text": "寝汗・ほてり・口の渇きがあって、眠りが浅いと感じますか？",
        "weights": {"yin_deficiency": 2},
    },
    {
        "id": "q11",
        "text": "むくみやすく、雨の日は体が重だるくなりやすいですか？",
        "weights": {"water_toxicity": 2},
    },
    {
        "id": "q12",
        "text": "頭が重い感じやめまい、天気で悪化する頭痛はありますか？",
        "weights": {"water_toxicity": 2, "qi_stagnation": 1},
    },
]


ANSWER_SCALE = {
    "よくある": 2,
    "ときどき": 1,
    "ほぼない": 0,
}


TYPE_LABELS = {
    "qi_deficiency": "気虚（ききょ）タイプ",
    "qi_stagnation": "気滞（きたい）タイプ",
    "blood_deficiency": "血虚（けっきょ）タイプ",
    "blood_stasis": "瘀血（おけつ）タイプ",
    "yin_deficiency": "陰虚（いんきょ）タイプ",
    "water_toxicity": "水毒（すいどく）タイプ",
}


TYPE_ADVICE = {
    "qi_deficiency": "無理を避け、消化にやさしい食事と十分な休息を意識しましょう。",
    "qi_stagnation": "軽い運動や深呼吸で巡りを整え、気分転換の時間を作りましょう。",
    "blood_deficiency": "睡眠をしっかり取り、鉄分・たんぱく質を含む食事を意識しましょう。",
    "blood_stasis": "長時間同じ姿勢を避け、体を冷やさないようにして巡りを促しましょう。",
    "yin_deficiency": "夜更かしを避け、辛味や刺激物を取りすぎない生活を心がけましょう。",
    "water_toxicity": "塩分を控えめにし、体を冷やしすぎずに適度な運動で水分代謝を助けましょう。",
}


TYPE_IMAGE_URLS = {
    "qi_deficiency": os.getenv("RESULT_IMAGE_QI_DEFICIENCY_URL", ""),
    "qi_stagnation": os.getenv("RESULT_IMAGE_QI_STAGNATION_URL", ""),
    "blood_deficiency": os.getenv("RESULT_IMAGE_BLOOD_DEFICIENCY_URL", ""),
    "blood_stasis": os.getenv("RESULT_IMAGE_BLOOD_STASIS_URL", ""),
    "yin_deficiency": os.getenv("RESULT_IMAGE_YIN_DEFICIENCY_URL", ""),
    "water_toxicity": os.getenv("RESULT_IMAGE_WATER_TOXICITY_URL", ""),
}

TYPE_IMAGE_PATHS = {
    "qi_deficiency": "assets/result_qi_deficiency.png",
    "qi_stagnation": "assets/result_qi_stagnation.png",
    "blood_deficiency": "assets/result_blood_deficiency.png",
    "blood_stasis": "assets/result_blood_stasis.png",
    "yin_deficiency": "assets/result_yin_deficiency.png",
    "water_toxicity": "assets/result_water_toxicity.png",
}


def get_result_image_url(constitution_type: str) -> str:
    manual_url = TYPE_IMAGE_URLS.get(constitution_type, "").strip()
    if manual_url.startswith("https://"):
        return manual_url

    # If image URLs are not manually configured, build URL from this server.
    # PUBLIC_BASE_URL should be something like https://xxxx.ngrok-free.app
    if PUBLIC_BASE_URL:
        image_path = TYPE_IMAGE_PATHS.get(constitution_type, "")
        if image_path:
            return f"{PUBLIC_BASE_URL}/{image_path}"
    return ""


user_states: Dict[str, Dict] = {}


def get_conversation_id(source: Dict) -> str:
    return (
        source.get("userId")
        or source.get("groupId")
        or source.get("roomId")
        or ""
    )


def verify_signature(body: bytes, signature: str) -> bool:
    if SKIP_LINE_SIGNATURE_VALIDATION:
        print("Signature validation skipped by env setting.")
        return True
    if not LINE_CHANNEL_SECRET:
        print("LINE_CHANNEL_SECRET is empty. Signature check failed.")
        return False
    digest = hmac.new(
        LINE_CHANNEL_SECRET.encode("utf-8"), body, hashlib.sha256
    ).digest()
    expected = base64.b64encode(digest).decode("utf-8")
    ok = hmac.compare_digest(expected, signature)
    if not ok:
        print("Signature mismatch.")
    return ok


def reply_message(reply_token: str, messages: List[Dict]) -> bool:
    if not LINE_CHANNEL_ACCESS_TOKEN:
        print("LINE_CHANNEL_ACCESS_TOKEN is empty. Skip reply.")
        return False

    url = "https://api.line.me/v2/bot/message/reply"
    payload = json.dumps({"replyToken": reply_token, "messages": messages}).encode("utf-8")
    req = request.Request(url, data=payload, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}")
    try:
        request.urlopen(req, timeout=10)
        print("LINE reply API success")
        return True
    except error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8")
        except Exception:
            detail = "<failed to read error body>"
        print(f"LINE reply API HTTPError: status={e.code}, body={detail}")
        if e.code in (401, 403):
            print(
                "Hint: LINE_CHANNEL_ACCESS_TOKEN may be invalid or from another channel."
            )
        return False
    except Exception as e:
        print(f"LINE reply API error: {e}")
        return False


def score_answer(state: Dict, question_index: int, answer_label: str) -> None:
    answer_value = ANSWER_SCALE.get(answer_label)
    if answer_value is None:
        return

    question = QUESTIONS[question_index]
    for constitution_type, weight in question["weights"].items():
        state["scores"][constitution_type] = state["scores"].get(constitution_type, 0) + (
            answer_value * weight
        )


def build_question_message(index: int) -> Dict:
    q = QUESTIONS[index]
    return {
        "type": "text",
        "text": f"【質問 {index + 1}/{len(QUESTIONS)}】\n{q['text']}",
        "quickReply": {
            "items": [
                {
                    "type": "action",
                    "action": {"type": "message", "label": "よくある", "text": "よくある"},
                },
                {
                    "type": "action",
                    "action": {"type": "message", "label": "ときどき", "text": "ときどき"},
                },
                {
                    "type": "action",
                    "action": {"type": "message", "label": "ほぼない", "text": "ほぼない"},
                },
            ]
        },
    }


def build_result_message(state: Dict) -> Dict:
    scores = state["scores"]
    sorted_types = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    main_type, main_score = sorted_types[0]
    second_type, second_score = sorted_types[1]
    gap = main_score - second_score
    if gap <= 1:
        result_body = (
            f"あなたは「{TYPE_LABELS[main_type]} × {TYPE_LABELS[second_type]}」の複合傾向です。"
            f"（{main_score}点 / {second_score}点）\n"
            f"主傾向: {TYPE_ADVICE[main_type]}\n"
            f"副傾向: {TYPE_ADVICE[second_type]}"
        )
    else:
        result_body = (
            f"あなたは「{TYPE_LABELS[main_type]}」の傾向です。（{main_score}点）\n"
            f"{TYPE_ADVICE[main_type]}\n"
            f"次点: {TYPE_LABELS[second_type]}（{second_score}点）"
        )

    return {
        "type": "text",
        "text": (
            "診断結果が出ました。\n\n"
            f"{result_body}\n\n"
            "※この診断はセルフチェックです。体調不良が続く場合は専門家にご相談ください。"
        ),
    }


def build_result_messages(state: Dict) -> List[Dict]:
    text_message = build_result_message(state)
    scores = state["scores"]
    main_type = sorted(scores.items(), key=lambda x: x[1], reverse=True)[0][0]
    image_url = get_result_image_url(main_type)

    if not image_url or not image_url.startswith("https://"):
        return [text_message]

    return [
        {
            "type": "image",
            "originalContentUrl": image_url,
            "previewImageUrl": image_url,
        },
        text_message,
    ]


def start_diagnosis(user_id: str, reply_token: str) -> None:
    user_states[user_id] = {
        "question_index": 0,
        "scores": {
            "qi_deficiency": 0,
            "qi_stagnation": 0,
            "blood_deficiency": 0,
            "blood_stasis": 0,
            "yin_deficiency": 0,
            "water_toxicity": 0,
        },
    }
    messages = [
        {"type": "text", "text": "体質診断をはじめます。各質問に3択で気軽に答えてください。"},
        build_question_message(0),
    ]
    reply_message(reply_token, messages)


def handle_text_message(conversation_id: str, reply_token: str, text: str) -> None:
    text = text.strip()
    print(f"Incoming text message: {text}")

    if text in ("体質診断", "診断開始", "スタート", "体質診断を始める"):
        start_diagnosis(conversation_id, reply_token)
        return
    if text == "相談したい":
        reply_message(
            reply_token,
            [
                {
                    "type": "text",
                    "text": (
                        "ご相談ありがとうございます。木月調剤薬局へお気軽にご連絡ください。"
                        " 体質やお悩みに合わせてご案内します。"
                    ),
                }
            ],
        )
        return
    if text == "セルフケア":
        reply_message(
            reply_token,
            [
                {
                    "type": "text",
                    "text": (
                        "まずは睡眠・食事・体を冷やさないことを意識しましょう。"
                        " 診断後はタイプ別アドバイスも表示されます。"
                    ),
                }
            ],
        )
        return
    if text == "レシピ":
        reply_message(
            reply_token,
            [
                {
                    "type": "text",
                    "text": (
                        "体を温めるスープや、消化にやさしい献立がおすすめです。"
                        " 診断後のタイプに合わせてご提案もできます。"
                    ),
                }
            ],
        )
        return
    if text == "ヘルプ":
        reply_message(
            reply_token,
            [
                {
                    "type": "text",
                    "text": (
                        "使い方: 1) 体質診断を押す 2) 12問に回答 3) 結果と画像を確認。"
                        " 途中で分からない場合は「相談したい」と送ってください。"
                    ),
                }
            ],
        )
        return
    if text == "この診断について":
        reply_message(
            reply_token,
            [
                {
                    "type": "text",
                    "text": (
                        "12問のセルフチェックで、体質傾向（気虚/気滞/血虚/瘀血/陰虚/水毒）を簡易判定します。"
                        " 体調不良が続く場合は医療機関や専門家へご相談ください。"
                    ),
                }
            ],
        )
        return

    state = user_states.get(conversation_id)
    if not state:
        reply_message(
            reply_token,
            [
                {
                    "type": "text",
                    "text": "リッチメニューの「診断開始」を押すか、「体質診断」と送信してください。",
                }
            ],
        )
        return

    if text not in ANSWER_SCALE:
        reply_message(
            reply_token,
            [
                {
                    "type": "text",
                    "text": "回答は「よくある / ときどき / ほぼない」から選んでください。",
                }
            ],
        )
        return

    idx = state["question_index"]
    score_answer(state, idx, text)
    idx += 1
    state["question_index"] = idx

    if idx >= len(QUESTIONS):
        result_messages = build_result_messages(state)
        user_states.pop(conversation_id, None)
        reply_message(reply_token, result_messages)
        return

    reply_message(reply_token, [build_question_message(idx)])


def handle_postback(conversation_id: str, reply_token: str, data: str) -> None:
    if data == "action=start_diagnosis":
        start_diagnosis(conversation_id, reply_token)
        return

    reply_message(
        reply_token,
        [{"type": "text", "text": "メニューの「診断開始」からお試しください。"}],
    )


class LineWebhookHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in ("/", "/health"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(
                json.dumps(
                    {
                        "ok": True,
                        "service": "kampo-line-bot",
                        "webhook_path": WEBHOOK_PATH,
                    },
                    ensure_ascii=False,
                ).encode("utf-8")
            )
            return

        requested = unquote(parsed.path.lstrip("/"))
        if not requested.startswith("assets/"):
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")
            return

        file_path = Path(requested).resolve()
        assets_root = Path("assets").resolve()
        if not str(file_path).startswith(str(assets_root)):
            self.send_response(403)
            self.end_headers()
            self.wfile.write(b"Forbidden")
            return

        if not file_path.exists() or not file_path.is_file():
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")
            return

        content_type = "application/octet-stream"
        if file_path.suffix.lower() == ".png":
            content_type = "image/png"
        elif file_path.suffix.lower() == ".svg":
            content_type = "image/svg+xml"
        elif file_path.suffix.lower() in (".html", ".htm"):
            content_type = "text/html; charset=utf-8"

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.end_headers()
        self.wfile.write(file_path.read_bytes())

    def do_POST(self):
        print(f"Incoming POST path: {self.path}")
        body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        signature = self.headers.get("X-Line-Signature", "")

        if not verify_signature(body, signature):
            self.send_response(403)
            self.end_headers()
            self.wfile.write(b"Invalid signature")
            return

        try:
            payload = json.loads(body.decode("utf-8"))
        except Exception as e:
            print(f"Invalid JSON payload: {e}")
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
            return

        events = payload.get("events", [])
        print(f"Webhook events count: {len(events)}")

        for event in events:
            reply_token = event.get("replyToken")
            source = event.get("source", {})
            conversation_id = get_conversation_id(source)
            event_type = event.get("type")
            print(
                f"Event received: type={event_type}, source_type={source.get('type')}, "
                f"has_reply_token={bool(reply_token)}, conversation_id={conversation_id or 'N/A'}"
            )

            if not reply_token:
                print("Skip event because replyToken is missing.")
                continue

            try:
                if event_type == "message":
                    message = event.get("message", {})
                    print(f"Message type: {message.get('type')}")
                    if message.get("type") == "text":
                        if not conversation_id:
                            reply_message(
                                reply_token,
                                [
                                    {
                                        "type": "text",
                                        "text": "会話IDが取得できませんでした。1:1トークからお試しください。",
                                    }
                                ],
                            )
                            continue
                        handle_text_message(
                            conversation_id, reply_token, message.get("text", "")
                        )
                elif event_type == "postback":
                    postback = event.get("postback", {})
                    if not conversation_id:
                        reply_message(
                            reply_token,
                            [
                                {
                                    "type": "text",
                                    "text": "会話IDが取得できませんでした。1:1トークからお試しください。",
                                }
                            ],
                        )
                        continue
                    handle_postback(conversation_id, reply_token, postback.get("data", ""))
                else:
                    print(f"Unhandled event type: {event_type}")
            except Exception as e:
                print(f"Webhook event handling error: {e}")
                reply_message(
                    reply_token,
                    [
                        {
                            "type": "text",
                            "text": "処理中にエラーが発生しました。もう一度お試しください。",
                        }
                    ],
                )

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")


if __name__ == "__main__":
    if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET:
        print(
            "Warning: LINE_CHANNEL_ACCESS_TOKEN / LINE_CHANNEL_SECRET が未設定です。"
            " healthcheckは通りますが、LINE Webhookは正常動作しません。"
        )

    server = HTTPServer(("0.0.0.0", PORT), LineWebhookHandler)
    print(f"LINE webhook server started on port {PORT}")
    print(f"Webhook endpoint: {WEBHOOK_PATH}")
    if PUBLIC_BASE_URL:
        print(f"Public callback URL: {PUBLIC_BASE_URL}{WEBHOOK_PATH}")
    server.serve_forever()
