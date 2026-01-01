import { useEffect, useMemo, useState } from 'react';
import {
  Box,
  Button,
  Chip,
  FormControl,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import { Title } from 'react-admin';
import { fetchWithAuth } from '../authProvider';

const DEFAULT_API_URL = import.meta.env.DEV
  ? 'http://localhost:8000'
  : 'https://api.teamcore.ir';
const API_URL = import.meta.env.VITE_API_URL || DEFAULT_API_URL;

type ActionStatus = 'all' | 'pending' | 'approved' | 'executed' | 'failed' | 'rejected';

type AssistantAction = {
  id: number;
  action_type: string;
  summary?: string | null;
  status: string;
  payload_json?: Record<string, unknown> | null;
  result_json?: Record<string, unknown> | null;
  error?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  approved_at?: string | null;
  executed_at?: string | null;
};

const formatTime = (value?: string | null) => {
  if (!value) return '-';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString('fa-IR', { timeZone: 'Asia/Tehran' });
};

export const AssistantActionsPage = () => {
  const [statusFilter, setStatusFilter] = useState<ActionStatus>('pending');
  const [actions, setActions] = useState<AssistantAction[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const filterQuery = useMemo(() => {
    if (statusFilter === 'all') return '';
    return JSON.stringify({ status: statusFilter });
  }, [statusFilter]);

  const loadActions = async () => {
    setLoading(true);
    setError(null);
    try {
      const query = new URLSearchParams({
        skip: '0',
        limit: '50',
        sort: 'created_at',
        order: 'desc',
      });
      if (filterQuery) query.set('filter', filterQuery);
      const response = await fetchWithAuth(`${API_URL}/admin/assistant/actions?${query}`);
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data?.detail || 'Unable to load actions.');
      }
      setActions(data.data || []);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unable to load actions.';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadActions();
  }, [filterQuery]);

  const updateStatus = async (actionId: number, action: 'approve' | 'reject') => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetchWithAuth(
        `${API_URL}/admin/assistant/actions/${actionId}/${action}`,
        { method: 'POST' }
      );
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data?.detail || 'Action update failed.');
      }
      await loadActions();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Action update failed.';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box sx={{ px: { xs: 2, md: 3 }, py: 2 }}>
      <Title title="تاییدیه‌ها" />
      <Stack spacing={2} sx={{ mb: 3 }}>
        <Typography variant="h4">تاییدیه‌ها</Typography>
        <Typography variant="body1" color="text.secondary">
          تغییرات پیشنهادی دستیار را قبل از اعمال بررسی و تایید کنید.
        </Typography>
      </Stack>

      <Paper sx={{ p: { xs: 2, md: 3 } }}>
        <Stack spacing={2}>
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} alignItems="center">
            <FormControl sx={{ minWidth: 220 }}>
              <InputLabel id="status-filter-label">وضعیت</InputLabel>
              <Select
                labelId="status-filter-label"
                label="وضعیت"
                value={statusFilter}
                onChange={event => setStatusFilter(event.target.value as ActionStatus)}
              >
                <MenuItem value="all">همه</MenuItem>
                <MenuItem value="pending">در انتظار</MenuItem>
                <MenuItem value="approved">تایید شده</MenuItem>
                <MenuItem value="executed">اجرا شده</MenuItem>
                <MenuItem value="failed">ناموفق</MenuItem>
                <MenuItem value="rejected">رد شده</MenuItem>
              </Select>
            </FormControl>
            <Button variant="outlined" onClick={loadActions} disabled={loading}>
              بروزرسانی
            </Button>
          </Stack>

          {error && (
            <Paper variant="outlined" sx={{ p: 1.5, borderColor: 'error.light' }}>
              <Typography variant="body2" color="error">
                {error}
              </Typography>
            </Paper>
          )}

          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>شناسه</TableCell>
                <TableCell>نوع</TableCell>
                <TableCell>خلاصه</TableCell>
                <TableCell>وضعیت</TableCell>
                <TableCell>زمان</TableCell>
                <TableCell>نتیجه</TableCell>
                <TableCell align="right">عملیات</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {actions.map(action => (
                <TableRow key={action.id}>
                  <TableCell>{action.id}</TableCell>
                  <TableCell>{action.action_type}</TableCell>
                  <TableCell>{action.summary || '-'}</TableCell>
                  <TableCell>
                    <Chip
                      size="small"
                      label={action.status}
                      color={action.status === 'pending' ? 'warning' : 'default'}
                    />
                  </TableCell>
                  <TableCell>{formatTime(action.created_at)}</TableCell>
                  <TableCell>
                    {action.error ? (
                      <Typography variant="caption" color="error">
                        {action.error}
                      </Typography>
                    ) : action.result_json ? (
                      <Typography variant="caption">انجام شد</Typography>
                    ) : (
                      '-'
                    )}
                  </TableCell>
                  <TableCell align="right">
                    {action.status === 'pending' ? (
                      <Stack direction="row" spacing={1} justifyContent="flex-end">
                        <Button
                          size="small"
                          variant="contained"
                          color="primary"
                          onClick={() => updateStatus(action.id, 'approve')}
                          disabled={loading}
                        >
                          تایید
                        </Button>
                        <Button
                          size="small"
                          variant="outlined"
                          color="secondary"
                          onClick={() => updateStatus(action.id, 'reject')}
                          disabled={loading}
                        >
                          رد
                        </Button>
                      </Stack>
                    ) : (
                      '-'
                    )}
                  </TableCell>
                </TableRow>
              ))}
              {actions.length === 0 && (
                <TableRow>
                  <TableCell colSpan={7}>
                    <Typography variant="body2" color="text.secondary">
                      برای این فیلتر موردی یافت نشد.
                    </Typography>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </Stack>
      </Paper>
    </Box>
  );
};
