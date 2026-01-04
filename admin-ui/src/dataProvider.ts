import type { DataProvider } from 'react-admin';
import { fetchWithAuth } from './authProvider';

const DEFAULT_API_URL = import.meta.env.DEV
  ? 'http://localhost:8000'
  : 'https://api.teamcore.ir';
const API_URL = import.meta.env.VITE_API_URL || DEFAULT_API_URL;

const parseResponse = async (response: Response) => {
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data?.detail || 'Request failed');
  }
  return data;
};

const buildQuery = (params: any) => {
  const { page, perPage } = params.pagination;
  const { field, order } = params.sort;
  const filter = params.filter || {};
  const query = new URLSearchParams();
  query.set('skip', String((page - 1) * perPage));
  query.set('limit', String(perPage));
  query.set('sort', field);
  query.set('order', order.toLowerCase());
  if (Object.keys(filter).length) {
    query.set('filter', JSON.stringify(filter));
  }
  return query.toString();
};

const dataProvider: DataProvider = {
  getList: async (resource, params) => {
    if (resource === 'settings') {
      const response = await fetchWithAuth(`${API_URL}/admin/settings`);
      const data = await parseResponse(response);
      return { data: [data], total: 1 };
    }
    if (resource === 'product-sync-runs') {
      const query = buildQuery(params);
      const response = await fetchWithAuth(
        `${API_URL}/admin/products/sync-runs?${query}`
      );
      const data = await parseResponse(response);
      return { data: data.data, total: data.total };
    }
    const query = buildQuery(params);
    const response = await fetchWithAuth(`${API_URL}/admin/${resource}?${query}`);
    const data = await parseResponse(response);
    return { data: data.data, total: data.total };
  },
  getOne: async (resource, params) => {
    if (resource === 'settings') {
      const response = await fetchWithAuth(`${API_URL}/admin/settings`);
      const data = await parseResponse(response);
      return { data };
    }
    const response = await fetchWithAuth(
      `${API_URL}/admin/${resource}/${params.id}`
    );
    const data = await parseResponse(response);
    return { data };
  },
  getMany: async (resource, params) => {
    const filter = { id: params.ids };
    const query = buildQuery({
      pagination: { page: 1, perPage: params.ids.length },
      sort: { field: 'id', order: 'ASC' },
      filter,
    });
    const response = await fetchWithAuth(`${API_URL}/admin/${resource}?${query}`);
    const data = await parseResponse(response);
    return { data: data.data };
  },
  getManyReference: async (resource, params) => {
    const filter = { ...params.filter, [params.target]: params.id };
    const query = buildQuery({ ...params, filter });
    const response = await fetchWithAuth(`${API_URL}/admin/${resource}?${query}`);
    const data = await parseResponse(response);
    return { data: data.data, total: data.total };
  },
  update: async (resource, params) => {
    if (resource === 'settings') {
      const response = await fetchWithAuth(`${API_URL}/admin/settings`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(params.data),
      });
      const data = await parseResponse(response);
      return { data };
    }
    const response = await fetchWithAuth(`${API_URL}/admin/${resource}/${params.id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params.data),
    });
    const data = await parseResponse(response);
    return { data };
  },
  create: async (resource, params) => {
    const response = await fetchWithAuth(`${API_URL}/admin/${resource}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params.data),
    });
    const data = await parseResponse(response);
    return { data };
  },
  delete: async (resource, params) => {
    const response = await fetchWithAuth(`${API_URL}/admin/${resource}/${params.id}`, {
      method: 'DELETE',
    });
    const data = await parseResponse(response);
    return { data: { id: params.id, ...data } };
  },
  updateMany: async () => ({ data: [] }),
  deleteMany: async () => ({ data: [] }),
};

export { dataProvider };
