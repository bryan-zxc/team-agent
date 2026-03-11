export const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function apiFetch(
  path: string,
  init?: RequestInit,
): Promise<Response> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });

  if (response.status === 401) {
    if (typeof window !== "undefined") {
      window.location.href = "/";
    }
    throw new Error("Not authenticated");
  }

  return response;
}

export type UploadResult = {
  uploaded: { path: string; size: number }[];
  errors: { filename: string; detail: string }[];
};

/**
 * Upload files via multipart form data.
 * Uses XMLHttpRequest instead of fetch for upload progress support.
 */
export function uploadFiles(
  projectId: string,
  files: FileList | File[],
  directory: string,
  onProgress?: (loaded: number, total: number) => void,
): { promise: Promise<UploadResult>; abort: () => void } {
  const xhr = new XMLHttpRequest();
  const formData = new FormData();
  formData.append("directory", directory);
  for (const file of files) {
    formData.append("files", file);
  }

  const promise = new Promise<UploadResult>((resolve, reject) => {
    xhr.open("POST", `${API_URL}/projects/${projectId}/files/upload`);
    xhr.withCredentials = true;

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onProgress) {
        onProgress(e.loaded, e.total);
      }
    };

    xhr.onload = () => {
      if (xhr.status === 401) {
        window.location.href = "/";
        reject(new Error("Not authenticated"));
        return;
      }
      if (xhr.status >= 400) {
        reject(new Error(`Upload failed (${xhr.status})`));
        return;
      }
      try {
        resolve(JSON.parse(xhr.responseText));
      } catch {
        reject(new Error("Invalid response"));
      }
    };

    xhr.onerror = () => reject(new Error("Upload failed"));
    xhr.send(formData);
  });

  return { promise, abort: () => xhr.abort() };
}
