import { useFrappeGetDocList } from "frappe-react-sdk";

export interface GRMProject {
  name: string;
  title: string;
  description: string;
}

export function useProjects() {
  return useFrappeGetDocList<GRMProject>("GRM Project", {
    filters: [["is_active", "=", 1]],
    fields: ["name", "title", "description"],
    orderBy: { field: "title", order: "asc" },
  });
}
