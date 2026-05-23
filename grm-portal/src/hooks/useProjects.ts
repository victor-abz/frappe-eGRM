import { useFrappeGetCall } from "frappe-react-sdk";

export interface GRMProject {
  name: string;
  title: string;
  description: string;
}

export interface GRMCategory {
  name: string;
  category_name: string;
}

interface HomeListingsResponse {
  message: {
    status: string;
    data: {
      projects: GRMProject[];
      categories: GRMCategory[];
    };
  };
}

export function useHomeListings() {
  const { data, ...rest } = useFrappeGetCall<HomeListingsResponse>(
    "egrm.api.public_submit.get_home_listings"
  );
  const payload = data?.message?.data;
  return {
    ...rest,
    projects: payload?.projects ?? [],
    categories: payload?.categories ?? [],
  };
}

export function useProjects() {
  const { projects, ...rest } = useHomeListings();
  return { ...rest, data: projects };
}
