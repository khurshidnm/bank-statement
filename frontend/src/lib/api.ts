import axios from "axios";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface TargetRecord {
  record_id: string;
  customer_name: string;
  email: string;
  transaction_amount: number;
  transaction_date: string;
  status?: string;
}

export interface TransformResponse {
  status: "success";
  filename: string;
  total_records_processed: number;
  data: TargetRecord[];
}

export interface TransformErrorResponse {
  status: "error";
  error_code: string;
  message: string;
}

export class TransformApiError extends Error {
  errorCode: string;

  constructor(errorCode: string, message: string) {
    super(message);
    this.name = "TransformApiError";
    this.errorCode = errorCode;
  }
}

export async function transformFile(
  file: File,
  onUploadProgress?: (percent: number) => void
): Promise<TransformResponse> {
  const formData = new FormData();
  formData.append("file", file);

  try {
    const response = await axios.post<TransformResponse>(
      `${API_URL}/api/v1/transform`,
      formData,
      {
        headers: { "Content-Type": "multipart/form-data" },
        onUploadProgress: (event) => {
          if (onUploadProgress && event.total) {
            onUploadProgress(Math.round((event.loaded / event.total) * 100));
          }
        },
      }
    );
    return response.data;
  } catch (err) {
    if (axios.isAxiosError(err) && err.response?.data) {
      const data = err.response.data as { detail?: TransformErrorResponse };
      const detail = data.detail;
      if (detail?.message) {
        throw new TransformApiError(detail.error_code ?? "UNKNOWN_ERROR", detail.message);
      }
    }
    throw new TransformApiError("NETWORK_ERROR", "Could not reach the transformation service.");
  }
}
