function karmaSortKey(entry) {
  if (entry.is_banned) return [2, 0];
  const match = String(entry.karma_cost ?? "").match(/\d+(?:[.,]\d+)?/);
  if (!match) return [1, 0];
  return [0, Number(match[0].replace(",", "."))];
}

export function compareHomebrewKarma(left, right, direction) {
  const [leftCategory, leftCost] = karmaSortKey(left);
  const [rightCategory, rightCost] = karmaSortKey(right);
  const categoryComparison = leftCategory - rightCategory;
  if (categoryComparison !== 0) return categoryComparison;
  const costComparison = direction === "asc" ? leftCost - rightCost : rightCost - leftCost;
  return costComparison || left.id - right.id;
}

export function nextHomebrewSort(current, field) {
  if (current.field !== field) return { field, direction: "desc" };
  return { field, direction: current.direction === "desc" ? "asc" : "desc" };
}
