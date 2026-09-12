'use strict';
// Decode without protobuf defaults: absent, explicit zero and nonzero stay distinct.
function decodePlaytime(raw, type) {
  const body = type.toObject(type.decode(Buffer.isBuffer(raw) ? raw : raw.toBuffer()), {longs: String, defaults: false});
  return (body.games || []).map(g => {
    const row = {appid: g.appid};
    for (const [source, target] of Object.entries({playtime_forever: 'playtime_forever',
      playtime_2weeks: 'playtime_2weeks', last_playtime: 'rtime_last_played'})) {
      row[target] = Object.hasOwn(g, source) ? g[source] : null;
    }
    return row;
  });
}
module.exports = {decodePlaytime};
