import { useFrappeGetCall } from "frappe-react-sdk";

export interface MobileAppInfo {
  available: boolean;
  version_name: string | null;
  download_url: string | null;
  file_size: number | null;
  release_notes: string | null;
  message?: string;
}

const DEFAULT: MobileAppInfo = {
  available: false,
  version_name: null,
  download_url: null,
  file_size: null,
  release_notes: null,
};

export function useMobileApp(): { info: MobileAppInfo; isLoading: boolean; error: unknown } {
  const { data, isLoading, error } = useFrappeGetCall<{ message: MobileAppInfo }>(
    "egrm.api.mobile_app.get_latest_app",
    {},
    undefined,
    { revalidateOnFocus: false }
  );

  return {
    info: data?.message ?? DEFAULT,
    isLoading,
    error,
  };
}
