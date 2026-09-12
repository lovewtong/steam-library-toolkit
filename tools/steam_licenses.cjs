'use strict';
// App-level differences mean "only via this category"; package evidence also preserves overlap.
function licenseEvidence(user) {
  const allPackages = user.getOwnedPackages({});
  const ownPackages = new Set(user.getOwnedPackages({excludeShared: true}));
  const paidPackages = new Set(user.getOwnedPackages({excludeFree: true}));
  const permanentPackages = new Set(user.getOwnedPackages({excludeExpiring: true}));
  const result = new Map();
  let complete = true;
  for (const id of allPackages) {
    const info = user.picsCache.packages[id]?.packageinfo;
    if (!info || (info.appids != null && !Array.isArray(info.appids))) { complete = false; continue; }
    for (const appid of info.appids || []) {
      if (!result.has(appid)) result.set(appid, {own: false, shared: false, free: false, expiring: false,
        package_ids: [], method: 'package_filter_evidence'});
      const row = result.get(appid);
      row.own ||= ownPackages.has(id);
      row.shared ||= !ownPackages.has(id);
      row.free ||= !paidPackages.has(id);
      row.expiring ||= !permanentPackages.has(id);
      row.package_ids.push(id);
    }
  }
  for (const row of result.values()) row.complete = complete;
  return {byApp: result, complete};
}
module.exports = {licenseEvidence};
