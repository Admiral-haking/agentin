import { fetchWithAuth } from '../authProvider';

type ErrorPayload = {
  detail?: string | { msg?: string } | Array<{ loc?: Array<string | number>; msg?: string }>;
  error?: string;
  message?: string;
  errors?: Record<string, string>;
};

const parseResponse = async (response: Response): Promise<ErrorPayload | any> => {
  const contentType = response.headers.get('content-type') || '';
  if (contentType.includes('application/json')) {
    try {
      return await response.json();
    } catch {
      return {};
    }
  }
  const text = await response.text();
  if (!text) return {};
  return { detail: text };
};

const getErrorMessage = (data: ErrorPayload, fallback: string) => {
  if (!data) return fallback;
  if (typeof data.detail === 'string' && data.detail.trim()) return data.detail;
  if (typeof data.error === 'string' && data.error.trim()) return data.error;
  if (typeof data.message === 'string' && data.message.trim()) return data.message;
  if (typeof data.detail === 'object' && (data.detail as any)?.msg) {
    return String((data.detail as any).msg);
  }
  return fallback;
};

const normalizeFieldErrors = (data: ErrorPayload) => {
  if (!data) return null;
  if (data.errors && typeof data.errors === 'object') {
    return { errors: data.errors };
  }
  if (Array.isArray(data.detail)) {
    const errors: Record<string, string> = {};
    for (const item of data.detail) {
      const loc = Array.isArray(item?.loc) ? item.loc : [];
      const fieldParts = loc.filter(part => part !== 'body' && part !== 'query' && part !== 'path');
      const fieldName =
        fieldParts.map(part => String(part)).join('.') ||
        (loc.length ? String(loc[loc.length - 1]) : 'non_field_error');
      const msg = item?.msg ? String(item.msg) : 'Invalid value';
      if (fieldName) {
        errors[fieldName] = msg;
      }
    }
    if (Object.keys(errors).length) {
      return { errors };
    }
  }
  return null;
};

const fetchJson = async (
  input: RequestInfo,
  init: RequestInit = {},
  fallbackMessage = 'درخواست ناموفق بود.'
) => {
  const response = await fetchWithAuth(input, init);
  const data = await parseResponse(response);
  if (!response.ok) {
    throw new Error(getErrorMessage(data, fallbackMessage));
  }
  return data;
};

export { fetchJson, getErrorMessage, normalizeFieldErrors, parseResponse };
