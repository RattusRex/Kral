export type HomebrewSortField = "title" | "content_type" | "karma_cost" | "source_url" | "notes";
export type SortDirection = "asc" | "desc";
export type HomebrewSortState = { field: HomebrewSortField; direction: SortDirection };

type KarmaSortableEntry = {
  id: number;
  karma_cost: number | string | null | undefined;
  is_banned: boolean;
};

export function compareHomebrewKarma(left: KarmaSortableEntry, right: KarmaSortableEntry, direction: SortDirection): number;
export function nextHomebrewSort(current: HomebrewSortState, field: HomebrewSortField): HomebrewSortState;
