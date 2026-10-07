'use strict';
// App-level differences mean "only via this category"; package evidence also preserves overlap.
function licenseEvidence(user) {
  const allPackages = user.getOwnedPackages({});
  const ownPackages = new Set(user.getOwnedPackages({excludeShared: true}));
  const paidPackages = new Set(user.getOwnedPackages({excludeFree: true}));
  const permanentPackages = new Set(user.getOwnedPackages({excludeExpiring: true}));
  const result = new Map();
  const owners = new Map();
  for (const license of user.licenses || []) {
    if (Number.isInteger(license.package_id) && Number.isInteger(license.owner_id) && license.owner_id > 0) {
      if (!owners.has(license.package_id)) owners.set(license.package_id, new Set());
      owners.get(license.package_id).add(license.owner_id);
    }
  }
  let complete = true;
  for (const id of allPackages) {
    const info = user.picsCache.packages[id]?.packageinfo;
    if (!info || (info.appids != null && !Array.isArray(info.appids))) { complete = false; continue; }
    for (const appid of info.appids || []) {
      if (!result.has(appid)) result.set(appid, {own: false, shared: false, free: false, expiring: false,
        package_ids: [], owner_account_ids: [], method: 'package_filter_evidence'});
      const row = result.get(appid);
      row.own ||= ownPackages.has(id);
      row.shared ||= !ownPackages.has(id);
      row.free ||= !paidPackages.has(id);
      row.expiring ||= !permanentPackages.has(id);
      row.package_ids.push(id);
      for (const owner of owners.get(id) || []) if (!row.owner_account_ids.includes(owner)) row.owner_account_ids.push(owner);
    }
  }
  for (const row of result.values()) row.complete = complete;
  return {byApp: result, complete};
}
module.exports = {licenseEvidence};
