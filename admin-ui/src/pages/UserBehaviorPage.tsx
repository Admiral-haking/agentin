import { useEffect, useMemo, useState } from 'react';
import {
  Box,
  Button,
  Card,
  CardContent,
  Divider,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography,
  Chip,
} from '@mui/material';
import { Title } from 'react-admin';
import { fetchWithAuth } from '../authProvider';

const DEFAULT_API_URL = import.meta.env.DEV
  ? 'http://localhost:8000'
  : 'https://api.teamcore.ir';
const API_URL = import.meta.env.VITE_API_URL || DEFAULT_API_URL;

type BehaviorSummary = Record<string, number>;
type BehaviorRecent = { pattern?: string; confidence?: number; reason?: string };

type BehaviorRow = {
  id: number;
  external_id: string;
  username?: string | null;
  last_pattern?: string | null;
  confidence?: number | null;
  updated_at?: string | null;
  last_reason?: string | null;
  last_message?: string | null;
  summary?: BehaviorSummary | null;
  recent?: BehaviorRecent[] | null;
};

const formatTime = (value?: string | null) => {
  if (!value) return '-';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString('fa-IR', { timeZone: 'Asia/Tehran' });
};

const buildSummaryText = (summary?: BehaviorSummary | null) => {
  if (!summary) return '-';
  const top = Object.entries(summary)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 3)
    .map(([key, value]) => `${key}:${value}`);
  return top.length ? top.join('، ') : '-';
};

const buildRecentText = (recent?: BehaviorRecent[] | null) => {
  if (!recent || !recent.length) return '-';
  return recent
    .map(item => `${item.pattern ?? '-'}(${item.confidence ?? '-'})`)
    .join('، ');
};

export const UserBehaviorPage = () => {
  const [items, setItems] = useState<BehaviorRow[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [externalIdFilter, setExternalIdFilter] = useState('');
  const [usernameFilter, setUsernameFilter] = useState('');
  const [skip, setSkip] = useState(0);
  const limit = 25;

  const filterPayload = useMemo(() => {
    const payload: Record<string, string> = {};
    if (externalIdFilter.trim()) payload.external_id = externalIdFilter.trim();
    if (usernameFilter.trim()) payload.username = usernameFilter.trim();
    return payload;
  }, [externalIdFilter, usernameFilter]);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const query = new URLSearchParams();
      query.set('skip', String(skip));
      query.set('limit', String(limit));
      query.set('sort', 'updated_at');
      query.set('order', 'desc');
      if (Object.keys(filterPayload).length) {
        query.set('filter', JSON.stringify(filterPayload));
      }
      const response = await fetchWithAuth(`${API_URL}/admin/behavior/users?${query}`);
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data?.detail || 'دریافت رفتار کاربران ناموفق بود.');
      }
      setItems(data.data || []);
      setTotal(data.total || 0);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'دریافت رفتار کاربران ناموفق بود.';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [skip, filterPayload]);

  const handleApplyFilters = () => {
    setSkip(0);
  };

  const handleClearFilters = () => {
    setExternalIdFilter('');
    setUsernameFilter('');
    setSkip(0);
  };

  const handlePrev = () => setSkip(prev => Math.max(0, prev - limit));
  const handleNext = () => setSkip(prev => prev + limit);

  const canPrev = skip > 0;
  const canNext = skip + limit < total;

  return (
    <Box sx={{ px: { xs: 2, md: 3 }, py: 2 }}>
      <Title title="رفتار کاربران" />
      <Stack spacing={2} sx={{ mb: 3 }}>
        <Typography variant="h4">رفتار کاربران</Typography>
        <Typography variant="body1" color="text.secondary">
          الگوی رفتاری هر کاربر از روی گفتگوها استخراج شده و در اینجا نمایش داده می‌شود.
        </Typography>
      </Stack>

      <Card sx={{ mb: 2 }}>
        <CardContent>
          <Stack spacing={2}>
            <Typography variant="h6">فیلترها</Typography>
            <Stack direction={{ xs: 'column', md: 'row' }} spacing={2}>
              <TextField
                label="شناسه کاربر (external_id)"
                value={externalIdFilter}
                onChange={event => setExternalIdFilter(event.target.value)}
                fullWidth
              />
              <TextField
                label="نام کاربری"
                value={usernameFilter}
                onChange={event => setUsernameFilter(event.target.value)}
                fullWidth
              />
            </Stack>
            <Stack direction="row" spacing={1}>
              <Button variant="contained" onClick={handleApplyFilters} disabled={loading}>
                اعمال فیلتر
              </Button>
              <Button variant="outlined" onClick={handleClearFilters} disabled={loading}>
                پاک کردن
              </Button>
            </Stack>
          </Stack>
        </CardContent>
      </Card>

      {error && (
        <Card sx={{ mb: 2 }}>
          <CardContent>
            <Typography color="error">{error}</Typography>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardContent>
          <Stack spacing={2}>
            <Stack direction="row" justifyContent="space-between" alignItems="center">
              <Typography variant="h6">نتایج ({total})</Typography>
              <Stack direction="row" spacing={1}>
                <Button variant="outlined" onClick={handlePrev} disabled={!canPrev || loading}>
                  قبلی
                </Button>
                <Button variant="outlined" onClick={handleNext} disabled={!canNext || loading}>
                  بعدی
                </Button>
              </Stack>
            </Stack>
            <Divider />
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>کاربر</TableCell>
                  <TableCell>الگوی اخیر</TableCell>
                  <TableCell>اعتماد</TableCell>
                  <TableCell>به‌روزرسانی</TableCell>
                  <TableCell>دلیل</TableCell>
                  <TableCell>خلاصه</TableCell>
                  <TableCell>نمونه‌ها</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {items.map(item => (
                  <TableRow key={item.id}>
                    <TableCell>
                      <Stack spacing={0.5}>
                        <Typography variant="body2">{item.username || '-'}</Typography>
                        <Typography variant="caption" color="text.secondary">
                          {item.external_id}
                        </Typography>
                      </Stack>
                    </TableCell>
                    <TableCell>
                      {item.last_pattern ? (
                        <Chip size="small" color="primary" label={item.last_pattern} />
                      ) : (
                        '-'
                      )}
                    </TableCell>
                    <TableCell>{item.confidence ?? '-'}</TableCell>
                    <TableCell>{formatTime(item.updated_at)}</TableCell>
                    <TableCell>{item.last_reason || '-'}</TableCell>
                    <TableCell>{buildSummaryText(item.summary)}</TableCell>
                    <TableCell>{buildRecentText(item.recent)}</TableCell>
                  </TableRow>
                ))}
                {!items.length && !loading && (
                  <TableRow>
                    <TableCell colSpan={7}>
                      <Typography variant="body2" color="text.secondary">
                        داده‌ای برای نمایش وجود ندارد.
                      </Typography>
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </Stack>
        </CardContent>
      </Card>
    </Box>
  );
};
