import { useQuery } from "@tanstack/react-query";
import { listFilesOptions } from "@/client/@tanstack/react-query.gen";

interface UseFileListParams {
  path: string;
  show_hidden?: boolean;
}

/** List directory contents at `path` via the `/api/files` endpoint. */
export function useFileList({ path, show_hidden }: UseFileListParams) {
  return useQuery(listFilesOptions({ query: { path, show_hidden } }));
}
