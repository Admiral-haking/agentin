import { useEffect, useMemo, useState } from 'react';
import {
  Box,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
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
  TextField,
  Typography,
} from '@mui/material';
import { Title } from 'react-admin';
import { fetchJson } from '../utils/api';
import { InlineAlert } from '../components/InlineAlert';

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
  const [editOpen, setEditOpen] = useState(false);
  const [editAction, setEditAction] = useState<AssistantAction | null>(null);
  const [editPayload, setEditPayload] = useState('');
  const [editSummary, setEditSummary] = useState('');
  const [editError, setEditError] = useState<string | null>(null);

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
      const data = await fetchJson(
        `${API_URL}/admin/assistant/actions?${query}`,
        {},
        'Unable to load actions.'
      );
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
      await fetchJson(
        `${API_URL}/admin/assistant/actions/${actionId}/${action}`,
        { method: 'POST' },
        'Action update failed.'
      );
      await loadActions();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Action update failed.';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const openEdit = (action: AssistantAction) => {
    setEditAction(action);
    setEditSummary(action.summary || '');
    setEditPayload(JSON.stringify(action.payload_json ?? {}, null, 2));
    setEditError(null);
    setEditOpen(true);
  };

  const closeEdit = () => {
    setEditOpen(false);
    setEditAction(null);
    setEditError(null);
  };

  const saveEdit = async () => {
    if (!editAction) return;
    let parsedPayload: Record<string, unknown> = {};
    try {
      const parsed = JSON.parse(editPayload || '{}');
      if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
        setEditError('Payload باید یک شیء JSON باشد.');
        return;
      }
      parsedPayload = parsed as Record<string, unknown>;
    } catch {
      setEditError('JSON نامعتبر است.');
      return;
    }
    setLoading(true);
    setEditError(null);
    try {
      await fetchJson(
        `${API_URL}/admin/assistant/actions/${editAction.id}`,
        {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            summary: editSummary || null,
            payload: parsedPayload,
          }),
        },
        'ویرایش اکشن ناموفق بود.'
      );
      await loadActions();
      closeEdit();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'ویرایش اکشن ناموفق بود.';
      setEditError(message);
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

          {error && <InlineAlert title="خطای بارگذاری" message={error} />}

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
                          variant="outlined"
                          onClick={() => openEdit(action)}
                          disabled={loading}
                        >
                          ویرایش
                        </Button>
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

      <Dialog open={editOpen} onClose={closeEdit} maxWidth="sm" fullWidth>
        <DialogTitle>ویرایش اکشن</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              label="خلاصه"
              value={editSummary}
              onChange={event => setEditSummary(event.target.value)}
              fullWidth
            />
            <TextField
              label="Payload JSON"
              value={editPayload}
              onChange={event => setEditPayload(event.target.value)}
              fullWidth
              multiline
              minRows={6}
              error={Boolean(editError)}
              helperText={editError || 'فیلدهای لازم را تکمیل کنید (مثل page_url یا id).'}
              sx={{ fontFamily: 'monospace' }}
            />
          </Stack>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={closeEdit} disabled={loading}>
            انصراف
          </Button>
          <Button onClick={saveEdit} variant="contained" disabled={loading}>
            ذخیره
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};
