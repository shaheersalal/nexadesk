"""
Twilio helpers: TwiML generation and webhook signature validation.
"""
from twilio.twiml.voice_response import VoiceResponse, Connect, Stream
from twilio.request_validator import RequestValidator

from app.config import get_settings

settings = get_settings()


def build_stream_twiml(call_sid: str) -> str:
    """
    TwiML that connects the call to our WebSocket media stream.
    Twilio sends audio to /voice/stream and receives TTS audio back.
    """
    response = VoiceResponse()
    connect = Connect()
    stream = Stream(
        url=f"{settings.TELEPHONY_WEBHOOK_BASE_URL.replace('http', 'ws')}/voice/stream/{call_sid}"
    )
    stream.parameter(name="call_sid", value=call_sid)
    connect.append(stream)
    response.append(connect)
    return str(response)


def build_fallback_twiml(message: str) -> str:
    """Simple <Say> response for error cases."""
    response = VoiceResponse()
    response.say(message, voice="alice")
    return str(response)


def validate_twilio_signature(url: str, params: dict, signature: str) -> bool:
    """Verify the request came from Twilio."""
    validator = RequestValidator(settings.TELEPHONY_AUTH_TOKEN)
    return validator.validate(url, params, signature)


def twilio_client():
    from twilio.rest import Client
    return Client(settings.TELEPHONY_ACCOUNT_SID, settings.TELEPHONY_AUTH_TOKEN)
