#[title: Vorto群管理]
#[language: python]
#[class: 工具类]
#[service: 203066880]
#[author: rujingxianghai]
#[version: 1.2]
#[platform: qq]
#[open_source: false]
#[public: true]
#[price: 0.1]
#[disable: false]
#[description: 自动同意加群 + 入群算数验证]
#[event: qq-notice-group_increase]
#[event: qq-request-group-add]

#[param: {"required":true,"key":"otto.math_valid_groups","bool":false,"placeholder":"","name":"开启验证群组","desc":"英文逗号分割"}]
#[param: {"required":true,"key":"otto.auto_approve_group","bool":true,"placeholder":"","name":"自动同意加群","desc":"开启后将自动同意加群请求"}]
#[param: {"required":true,"key":"otto.math_valid_disable","bool":true,"placeholder":"","name":"关闭算术","desc":"勾选后只发欢迎语，不再进行算术验证"}]
#[param: {"required":true,"key":"otto.math_valid_welcome","bool":false,"placeholder":"","name":"欢迎语","desc":""}]
#[param: {"required":true,"key":"otto.math_valid_reject","bool":false,"placeholder":"","name":"拒绝语","desc":""}]


import json
import random
import re
import time

import middleware

SUPPORTED_EVENT_TYPES = {
    "qq-notice-group_increase",
    "qq-request-group-add",
}
VERIFY_TIMEOUT_MS = 90000
VERIFY_TIMEOUT_TEXT = "90秒"
DEFAULT_WELCOME = "✅欢迎加入本群！\n请认真阅读群公告，遵守群规，谢谢合作！"
DEFAULT_REJECT = "❌很遗憾，稍后你将被移出群聊！"

sender_id = middleware.getSenderID()
sender = middleware.Sender(sender_id)


def to_bool(value):
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes", "on"}


def load_config():
    return {
        "groups": sender.bucketGet("otto", "math_valid_groups") or "",
        "disable": to_bool(sender.bucketGet("otto", "math_valid_disable")),
        "welcome": sender.bucketGet("otto", "math_valid_welcome") or DEFAULT_WELCOME,
        "reject": sender.bucketGet("otto", "math_valid_reject") or DEFAULT_REJECT,
    }


def parse_group_ids(groups_text):
    if not groups_text:
        return set()

    normalized = str(groups_text).replace("，", ",")
    return {item.strip() for item in normalized.split(",") if item.strip()}


def parse_event_data(raw_event_data):
    if not raw_event_data:
        return {}

    try:
        return json.loads(raw_event_data)
    except json.JSONDecodeError:
        return {}


def resolve_user_and_group(event_obj):
    user_id = event_obj.get("user_id") or sender.getUserID()
    chat_id = event_obj.get("group_id") or sender.getChatID()
    return str(user_id).strip(), str(chat_id).strip()


def generate_question():
    left = f"{random.randint(0, 99):02d}"
    right = f"{random.randint(0, 99):02d}"
    return left, right, int(left) + int(right)


def parse_answer(answer_text):
    if answer_text is None:
        return None

    match = re.match(r"^[+-]?\d+", str(answer_text).strip())
    if not match:
        return None

    try:
        return int(match.group(0))
    except ValueError:
        return None


def mention_message(user_id, content):
    return f"[CQ:at,qq={user_id}]\n{content}"


def send_welcome(user_id, welcome_text):
    sender.reply(mention_message(user_id, welcome_text))


def reject_and_kick(user_id, reject_text):
    sender.reply(mention_message(user_id, reject_text))
    time.sleep(1)
    sender.groupKick(user_id)


def handle_group_increase():
    event_type = str(sender.getEventType() or "").strip()
    if event_type and event_type not in SUPPORTED_EVENT_TYPES:
        return

    config = load_config()
    enabled_groups = parse_group_ids(config["groups"])
    if not enabled_groups:
        return

    event_obj = parse_event_data(sender.getEventData())
    user_id, chat_id = resolve_user_and_group(event_obj)
    if not user_id or not chat_id or chat_id not in enabled_groups:
        return

    if config["disable"]:
        send_welcome(user_id, config["welcome"])
        return

    left, right, result = generate_question()
    sender.reply(
        mention_message(
            user_id,
            f"为了验证你不是机器人，请在【{VERIFY_TIMEOUT_TEXT}】内将下面题目的正确答案发到群内，否则你将被移出群聊！\n{left}+{right}= ?",
        )
    )

    user_answer = sender.input(VERIFY_TIMEOUT_MS, 0, False)
    if parse_answer(user_answer) == result:
        send_welcome(user_id, config["welcome"])
        return

    reject_and_kick(user_id, config["reject"])


def handle_group_add_request():
    """处理加群请求（qq-request-group-add）：自动同意开关开启时，
    自动同意「开启验证群组」（math_valid_groups）内的加群请求。"""
    event_type = str(sender.getEventType() or "").strip()
    if event_type != "qq-request-group-add":
        return

    # 自动同意开关（otto.auto_approve_group，默认关）
    if not to_bool(sender.bucketGet("otto", "auto_approve_group")):
        return

    # 只处理「开启验证群组」内的加群请求（复用 math_valid_groups）
    config = load_config()
    enabled_groups = parse_group_ids(config["groups"])
    if not enabled_groups:
        return

    event_obj = parse_event_data(sender.getEventData())
    user_id, chat_id = resolve_user_and_group(event_obj)
    flag = str(event_obj.get("flag") or "").strip()
    if not user_id or not chat_id or not flag or chat_id not in enabled_groups:
        return

    sender.groupAddRequest(flag, approve=True)
    print(f"Vorto已自动同意加群请求：群={chat_id} 用户={user_id}")


def main():
    try:
        event_type = str(sender.getEventType() or "").strip()
        if event_type == "qq-request-group-add":
            handle_group_add_request()
        else:
            handle_group_increase()
    except Exception as exc:
        print(f"Vorto群管理插件执行异常: {exc}")


main()
