'use strict';
function eligible(msg, start, mode, testNumber) {
    return !msg.fromMe && !msg.isStatus && typeof msg.from === 'string' &&
        /@(c\.us|lid)$/.test(msg.from) && msg.timestamp >= start &&
        (mode === 'all' || msg.from === testNumber + '@c.us') &&
        (msg.type === 'chat' || msg.type === 'ptt' || msg.type === 'audio');
}
function acceptOnce(seen, msg) {
    const raw = msg.id;
    const id = typeof raw === 'string' ? raw : raw?._serialized ||
        (raw?.id ? [msg.from, raw.fromMe, raw.id].join(':') :
        (msg.timestamp ? [msg.from, msg.timestamp, msg.type, require('crypto').createHash('sha256').update(msg.body || '').update(String(msg._data?.filehash || '')).digest('hex')].join(':') : null));
    // A missing identifier must never place undefined in the deduplication set:
    // that would silently discard every later message without an identifier.
    if (!id) return true;
    if (seen.has(id)) return false;
    seen.add(id);
    if (seen.size > 5000) seen.delete(seen.values().next().value);
    return true;
}
module.exports = { eligible, acceptOnce };
