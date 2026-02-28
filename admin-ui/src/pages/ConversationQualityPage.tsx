import { useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Divider,
  Grid,
  LinearProgress,
  MenuItem,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import { Link } from 'react-router-dom';
import { Title } from 'react-admin';
import { fetchJson } from '../utils/api';

const DEFAULT_API_URL = import.meta.env.DEV
  ? 'http://localhost:8000'
  : 'https://api.teamcore.ir';
const API_URL = import.meta.env.VITE_API_URL || DEFAULT_API_URL;

type QualityPayload = {
  window_days: number;
  counts: Record<string, number>;
  rates: Record<string, number>;
  top_repetitive_templates: Array<{ text: string; count: number }>;
  recommended_actions: string[];
};

type PolicyItem = {
  text: string;
  priority: 'critical' | 'high' | 'normal';
  kind: 'rule' | 'event' | 'campaign' | 'note';
  source: string;
  created_at?: string | null;
};

type PolicyPayload = {
  data: PolicyItem[];
  formatted?: string | null;
};

const priorityLabel: Record<string, string> = {
  critical: 'بحرانی',
  high: 'مهم',
  normal: 'عادی',
};

const kindLabel: Record<string, string> = {
  rule: 'قانون',
  event: 'ایونت',
  campaign: 'کمپین',
  note: 'یادداشت',
};

const percent = (value?: number) => `${Math.round((value || 0) * 100)}%`;

const formatDate = (value?: string | null) => {
  if (!value) return '-';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString('fa-IR', { timeZone: 'Asia/Tehran' });
};

export const ConversationQualityPage = () => {
  const [days, setDays] = useState(30);
  const [loading, setLoading] = useState(false);
  const [quality, setQuality] = useState<QualityPayload | null>(null);
  const [policy, setPolicy] = useState<PolicyPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [policyText, setPolicyText] = useState('');
  const [policyPriority, setPolicyPriority] = useState<'critical' | 'high' | 'normal'>('high');
  const [policyKind, setPolicyKind] = useState<'rule' | 'event' | 'campaign' | 'note'>('rule');

  const loadData = async (windowDays = days, options?: { keepNotice?: boolean }) => {
    setLoading(true);
    setError(null);
    if (!options?.keepNotice) {
      setSuccess(null);
    }
    try {
      const [qualityData, policyData] = await Promise.all([
        fetchJson(
          `${API_URL}/admin/analytics/conversation-quality?days=${windowDays}`,
          {},
          'دریافت گزارش کیفیت مکالمه ناموفق بود.'
        ),
        fetchJson(
          `${API_URL}/admin/analytics/policy-memory?limit=12`,
          {},
          'دریافت حافظه سیاست‌ها ناموفق بود.'
        ),
      ]);
      setQuality(qualityData);
      setPolicy(policyData);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : 'دریافت اطلاعات کیفیت مکالمه ناموفق بود.';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData(30);
  }, []);

  const genericRate = quality?.rates?.generic_reply_rate || 0;
  const unknownRate = quality?.rates?.unknown_intent_rate || 0;
  const loopRate = quality?.rates?.loop_rate || 0;

  const qualityScore = useMemo(() => {
    const raw = 100 - (genericRate * 55 + unknownRate * 30 + loopRate * 15) * 100;
    return Math.max(0, Math.min(100, Math.round(raw)));
  }, [genericRate, unknownRate, loopRate]);

  const handleApplyWindow = () => {
    const safe = Math.max(1, Math.min(180, Number(days) || 30));
    setDays(safe);
    loadData(safe);
  };

  const handleAddPolicy = async () => {
    setError(null);
    setSuccess(null);
    if (!policyText.trim()) {
      setError('متن سیاست را وارد کنید.');
      return;
    }
    setLoading(true);
    try {
      const result = await fetchJson(
        `${API_URL}/admin/analytics/policy-memory`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            text: policyText.trim(),
            priority: policyPriority,
            kind: policyKind,
          }),
        },
        'ثبت سیاست ناموفق بود.'
      );
      if (result?.created) {
        setSuccess('سیاست جدید ذخیره شد و وارد حافظه اجرایی گردید.');
      } else {
        setSuccess('سیاست تکراری بود؛ حافظه تغییر نکرد.');
      }
      setPolicyText('');
      await loadData(days, { keepNotice: true });
    } catch (err) {
      const message = err instanceof Error ? err.message : 'ثبت سیاست ناموفق بود.';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const handleResetPolicy = async () => {
    setError(null);
    setSuccess(null);
    setLoading(true);
    try {
      await fetchJson(
        `${API_URL}/admin/analytics/policy-memory/reset`,
        { method: 'POST' },
        'ریست حافظه سیاست‌ها ناموفق بود.'
      );
      setSuccess('حافظه سیاست‌ها ریست شد.');
      await loadData(days, { keepNotice: true });
    } catch (err) {
      const message = err instanceof Error ? err.message : 'ریست حافظه سیاست‌ها ناموفق بود.';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box sx={{ px: { xs: 2, md: 3 }, py: 2 }}>
      <Title title="کیفیت مکالمه و سیاست‌ها" />
      <Card
        sx={{
          mb: 2.5,
          borderRadius: 3,
          background:
            'linear-gradient(135deg, rgba(15,139,141,0.22) 0%, rgba(31,66,122,0.14) 45%, rgba(242,143,84,0.18) 100%)',
        }}
      >
        <CardContent>
          <Stack spacing={1.5}>
            <Typography variant="h4">مرکز کیفیت مکالمه</Typography>
            <Typography variant="body1" color="text.secondary">
              پایش خطاهای واقعی گفتگو + حافظه سیاست‌های اجرایی ادمین با اولویت.
            </Typography>
            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5} alignItems={{ xs: 'stretch', sm: 'center' }}>
              <Chip
                label={`امتیاز کیفیت: ${qualityScore}/100`}
                color={qualityScore >= 75 ? 'success' : qualityScore >= 50 ? 'warning' : 'error'}
              />
              <TextField
                label="بازه تحلیل (روز)"
                type="number"
                value={days}
                onChange={event => setDays(Number(event.target.value))}
                size="small"
                sx={{ width: 170, bgcolor: 'rgba(255,255,255,0.72)', borderRadius: 2 }}
              />
              <Button variant="contained" onClick={handleApplyWindow} disabled={loading}>
                بروزرسانی تحلیل
              </Button>
            </Stack>
          </Stack>
        </CardContent>
      </Card>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      {success && <Alert severity="success" sx={{ mb: 2 }}>{success}</Alert>}

      <Grid container spacing={2}>
        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Typography variant="subtitle2" color="text.secondary">Generic Reply</Typography>
              <Typography variant="h5">{percent(genericRate)}</Typography>
              <LinearProgress
                variant="determinate"
                value={Math.min(100, (genericRate || 0) * 100)}
                color={genericRate <= 0.1 ? 'success' : genericRate <= 0.2 ? 'warning' : 'error'}
                sx={{ mt: 1 }}
              />
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Typography variant="subtitle2" color="text.secondary">Unknown Intent</Typography>
              <Typography variant="h5">{percent(unknownRate)}</Typography>
              <LinearProgress
                variant="determinate"
                value={Math.min(100, (unknownRate || 0) * 100)}
                color={unknownRate <= 0.12 ? 'success' : unknownRate <= 0.2 ? 'warning' : 'error'}
                sx={{ mt: 1 }}
              />
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Typography variant="subtitle2" color="text.secondary">Loop Rate</Typography>
              <Typography variant="h5">{percent(loopRate)}</Typography>
              <LinearProgress
                variant="determinate"
                value={Math.min(100, (loopRate || 0) * 100)}
                color={loopRate <= 0.06 ? 'success' : loopRate <= 0.1 ? 'warning' : 'error'}
                sx={{ mt: 1 }}
              />
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Typography variant="subtitle2" color="text.secondary">Rewrites / Guardrail</Typography>
              <Typography variant="h5">{quality?.counts?.guardrail_rewrites ?? 0}</Typography>
              <Typography variant="caption" color="text.secondary">
                window: {quality?.window_days ?? days} days
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={7}>
          <Card>
            <CardContent>
              <Stack spacing={1.5}>
                <Typography variant="h6">اقدام‌های پیشنهادی</Typography>
                <Divider />
                {(quality?.recommended_actions || []).map((action, index) => (
                  <Typography key={`${action}-${index}`} variant="body2">
                    {index + 1}. {action}
                  </Typography>
                ))}
                <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.2} sx={{ pt: 1 }}>
                  <Button component={Link} to="/ai-context" variant="contained">
                    بررسی کانتکست هوش
                  </Button>
                  <Button component={Link} to="/settings" variant="outlined">
                    تنظیمات پاسخ
                  </Button>
                  <Button component={Link} to="/logs" variant="outlined">
                    لاگ‌های جزئی
                  </Button>
                </Stack>
              </Stack>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={5}>
          <Card>
            <CardContent>
              <Stack spacing={1.5}>
                <Typography variant="h6">الگوهای تکراری پاسخ</Typography>
                <Divider />
                {(quality?.top_repetitive_templates || []).length === 0 && (
                  <Typography variant="body2" color="text.secondary">الگوی تکراری بحرانی دیده نشد.</Typography>
                )}
                {(quality?.top_repetitive_templates || []).map((item, index) => (
                  <Box
                    key={`${item.text}-${index}`}
                    sx={{ p: 1.25, borderRadius: 2, bgcolor: 'rgba(15,139,141,0.07)' }}
                  >
                    <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 0.7 }}>
                      <Chip size="small" color="warning" label={`x${item.count}`} />
                    </Stack>
                    <Typography variant="caption">{item.text}</Typography>
                  </Box>
                ))}
              </Stack>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={5}>
          <Card>
            <CardContent>
              <Stack spacing={1.5}>
                <Typography variant="h6">ثبت سیاست جدید</Typography>
                <TextField
                  label="متن سیاست/دستور اجرایی"
                  value={policyText}
                  onChange={event => setPolicyText(event.target.value)}
                  multiline
                  minRows={4}
                  fullWidth
                />
                <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1}>
                  <TextField
                    select
                    label="اولویت"
                    value={policyPriority}
                    onChange={event => setPolicyPriority(event.target.value as 'critical' | 'high' | 'normal')}
                    fullWidth
                  >
                    <MenuItem value="critical">بحرانی</MenuItem>
                    <MenuItem value="high">مهم</MenuItem>
                    <MenuItem value="normal">عادی</MenuItem>
                  </TextField>
                  <TextField
                    select
                    label="نوع"
                    value={policyKind}
                    onChange={event => setPolicyKind(event.target.value as 'rule' | 'event' | 'campaign' | 'note')}
                    fullWidth
                  >
                    <MenuItem value="rule">قانون</MenuItem>
                    <MenuItem value="event">ایونت</MenuItem>
                    <MenuItem value="campaign">کمپین</MenuItem>
                    <MenuItem value="note">یادداشت</MenuItem>
                  </TextField>
                </Stack>
                <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1}>
                  <Button variant="contained" onClick={handleAddPolicy} disabled={loading}>
                    ذخیره در حافظه
                  </Button>
                  <Button variant="outlined" color="error" onClick={handleResetPolicy} disabled={loading}>
                    ریست حافظه
                  </Button>
                </Stack>
              </Stack>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={7}>
          <Card>
            <CardContent>
              <Stack spacing={1.5}>
                <Typography variant="h6">حافظه سیاست‌های فعال</Typography>
                <Divider />
                {(policy?.data || []).length === 0 && (
                  <Typography variant="body2" color="text.secondary">
                    موردی در حافظه فعال ثبت نشده است.
                  </Typography>
                )}
                {(policy?.data || []).map((item, index) => (
                  <Box
                    key={`${item.text}-${index}`}
                    sx={{
                      p: 1.4,
                      borderRadius: 2.2,
                      bgcolor:
                        item.priority === 'critical'
                          ? 'rgba(209,76,76,0.12)'
                          : item.priority === 'high'
                            ? 'rgba(240,163,74,0.14)'
                            : 'rgba(61,111,171,0.12)',
                    }}
                  >
                    <Stack
                      direction={{ xs: 'column', sm: 'row' }}
                      justifyContent="space-between"
                      alignItems={{ xs: 'flex-start', sm: 'center' }}
                      spacing={1}
                    >
                      <Stack direction="row" spacing={1}>
                        <Chip size="small" label={priorityLabel[item.priority] || item.priority} />
                        <Chip size="small" variant="outlined" label={kindLabel[item.kind] || item.kind} />
                      </Stack>
                      <Typography variant="caption" color="text.secondary">
                        {formatDate(item.created_at)}
                      </Typography>
                    </Stack>
                    <Typography variant="body2" sx={{ mt: 1 }}>
                      {item.text}
                    </Typography>
                  </Box>
                ))}
              </Stack>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
};
