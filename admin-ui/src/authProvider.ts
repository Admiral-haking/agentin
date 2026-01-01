import type { AuthProvider } from 'react-admin';

const DEFAULT_API_URL = import.meta.env.DEV
  ? 'http://localhost:8000'
  : 'https://api.teamcore.ir';
const API_URL = import.meta.env.VITE_API_URL || DEFAULT_API_URL;
const ACCESS_TOKEN_KEY = 'dm_bot_access_token';
const REFRESH_TOKEN_KEY = 'dm_bot_refresh_token';
const ROLE_KEY = 'dm_bot_role';

const getAccessToken = () => localStorage.getItem(ACCESS_TOKEN_KEY);

const setTokens = (access: string, refresh: string) => {
  localStorage.setItem(ACCESS_TOKEN_KEY, access);
  localStorage.setItem(REFRESH_TOKEN_KEY, refresh);
};

const clearTokens = () => {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
  localStorage.removeItem(ROLE_KEY);
};

const refreshAccessToken = async () => {
  const refreshToken = localStorage.getItem(REFRESH_TOKEN_KEY);
  if (!refreshToken) throw new Error('Missing refresh token');
  const response = await fetch(`${API_URL}/auth/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
  if (!response.ok) {
    clearTokens();
    throw new Error('Unable to refresh token');
  }
  const data = await response.json();
  setTokens(data.access_token, data.refresh_token);
  return data.access_token as string;
};

const fetchWithAuth = async (input: RequestInfo, init: RequestInit = {}) => {
  let token = getAccessToken();
  const headers = new Headers(init.headers || {});
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }
  const response = await fetch(input, { ...init, headers });
  if (response.status === 401) {
    token = await refreshAccessToken();
    headers.set('Authorization', `Bearer ${token}`);
    return fetch(input, { ...init, headers });
  }
  return response;
};

const authProvider: AuthProvider = {
  login: async ({ username, password }) => {
    const response = await fetch(`${API_URL}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });
    if (!response.ok) throw new Error('Invalid credentials');
    const data = await response.json();
    setTokens(data.access_token, data.refresh_token);
  },
  logout: async () => {
    clearTokens();
  },
  checkError: async (error) => {
    if (error?.status === 401 || error?.status === 403) {
      clearTokens();
      throw error;
    }
  },
  checkAuth: async () => {
    const token = getAccessToken();
    if (!token) {
      await refreshAccessToken();
    }
  },
  getPermissions: async () => {
    const response = await fetchWithAuth(`${API_URL}/auth/me`);
    if (!response.ok) return 'staff';
    const data = await response.json();
    const role = data.role || 'staff';
    localStorage.setItem(ROLE_KEY, role);
    return role;
  },
  getIdentity: async () => {
    const response = await fetchWithAuth(`${API_URL}/auth/me`);
    if (!response.ok) throw new Error('Unable to load identity');
    const data = await response.json();
    return { id: data.id, fullName: data.username };
  },
};

export { authProvider, getAccessToken, fetchWithAuth };
