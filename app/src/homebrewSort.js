function statusText(entry) {
  return entry.status_text ?? (typeof entry.karma_cost === "string" ? entry.karma_cost : "");
}

export function homebrewKarmaSortKey(entry) {
  if (Number.isFinite(entry.karma_cost)) return { group: 0, value: entry.karma_cost };
  const rangeStart = String(statusText(entry)).match(/\d+/)?.[0];
  if (rangeStart !== undefined) return { group: 0, value: Number(rangeStart) };
  if (entry.is_banned) return { group: 1, value: 0 };
  return { group: 2, value: 0 };
}

export function compareHomebrewKarma(left, right, direction) {
  const leftKey = homebrewKarmaSortKey(left);
  const rightKey = homebrewKarmaSortKey(right);
  if (leftKey.group !== rightKey.group) return leftKey.group - rightKey.group;
  if (leftKey.group !== 0) return 0;
  return direction === "asc" ? leftKey.value - rightKey.value : rightKey.value - leftKey.value;
}

export function nextHomebrewSort(current, field) {
  if (current.field !== field) return { field, direction: field === "karma_cost" ? "desc" : "asc" };
  return { field, direction: current.direction === "asc" ? "desc" : "asc" };
}
