import pyrogram.utils as _utils
import pyrogram.client as _client

_MIN_CHANNEL_ID = -1009999999999

if _utils.MIN_CHANNEL_ID > _MIN_CHANNEL_ID:
    _utils.MIN_CHANNEL_ID = _MIN_CHANNEL_ID


def _patched_get_peer_type(peer_id: int) -> str:
    if peer_id < 0:
        if -2147483647 <= peer_id:
            return "chat"
        if _MIN_CHANNEL_ID <= peer_id:
            return "channel"
    elif 0 < peer_id <= 999999999999:
        return "user"
    raise ValueError(f"Peer id invalid: {peer_id}")


_utils.get_peer_type = _patched_get_peer_type


_original_handle_updates = _client.Client.handle_updates


async def _patched_handle_updates(self, updates):
    try:
        return await _original_handle_updates(self, updates)
    except Exception:
        pass


_client.Client.handle_updates = _patched_handle_updates
