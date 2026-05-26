from __future__ import annotations

from xml.etree import ElementTree


class WeComMessageParseError(ValueError):
    pass


def _parse_xml(xml_text: str) -> ElementTree.Element:
    if "<!DOCTYPE" in xml_text.upper() or "<!ENTITY" in xml_text.upper():
        raise WeComMessageParseError("UNSAFE_XML")
    try:
        return ElementTree.fromstring(xml_text)
    except ElementTree.ParseError as exc:
        raise WeComMessageParseError("INVALID_XML") from exc


def extract_encrypted_payload(wrapper_xml: str) -> str:
    root = _parse_xml(wrapper_xml)
    encrypted = root.findtext("Encrypt", default="").strip()
    if not encrypted:
        raise WeComMessageParseError("MISSING_ENCRYPT")
    return encrypted


def parse_message(xml_text: str) -> dict[str, object]:
    root = _parse_xml(xml_text)

    def value(tag: str) -> str:
        return root.findtext(tag, default="").strip()

    create_time = value("CreateTime")
    return {
        "to_user_name": value("ToUserName"),
        "from_user_name": value("FromUserName"),
        "create_time": int(create_time) if create_time.isdigit() else 0,
        "msg_type": value("MsgType").lower(),
        "pic_url": value("PicUrl"),
        "media_id": value("MediaId"),
        "msg_id": value("MsgId"),
        "agent_id": value("AgentID"),
    }
