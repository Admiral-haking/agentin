import { useState } from 'react';
import {
  Box,
  Button,
  Card,
  CardContent,
  Divider,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import { Title } from 'react-admin';
import { fetchJson } from '../utils/api';

const DEFAULT_API_URL = import.meta.env.DEV
  ? 'http://localhost:8000'
  : 'https://api.teamcore.ir';
const API_URL = import.meta.env.VITE_API_URL || DEFAULT_API_URL;

type AiContextResponse = {
  user: { id: number; external_id: string; username?: string | null };
  context: string;
  sections: Record<string, any>;
};

export const AiContextPage = () => {
  const [conversationId, setConversationId] = useState('');
  const [userId, setUserId] = useState('');
  const [externalId, setExternalId] = useState('');
  const [result, setResult] = useState<AiContextResponse | null>(null);
  const [simulateMessage, setSimulateMessage] = useState('');
  const [simulateResult, setSimulateResult] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [clearNotice, setClearNotice] = useState<string | null>(null);
  const [pinNotice, setPinNotice] = useState<string | null>(null);
  const [pinProductId, setPinProductId] = useState('');

  const loadContext = async () => {
    setLoading(true);
    setError(null);
    setClearNotice(null);
    setPinNotice(null);
    try {
      const query = new URLSearchParams();
      if (conversationId.trim()) {
        query.set('conversation_id', conversationId.trim());
      } else if (userId.trim()) {
        query.set('user_id', userId.trim());
      } else if (externalId.trim()) {
        query.set('external_id', externalId.trim());
      } else {
        throw new Error('شناسه گفتگو یا کاربر را وارد کنید.');
      }
      const data = await fetchJson(
        `${API_URL}/admin/ai/context?${query}`,
        {},
        'دریافت کانتکست ناموفق بود.'
      );
      setResult(data);
      setSimulateResult(null);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'دریافت کانتکست ناموفق بود.';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const handleSimulate = async () => {
    setLoading(true);
    setError(null);
    setClearNotice(null);
    setPinNotice(null);
    try {
      if (!conversationId.trim()) {
        throw new Error('برای شبیه‌سازی باید conversation_id وارد شود.');
      }
      const data = await fetchJson(
        `${API_URL}/admin/ai/simulate_reply`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            conversation_id: Number(conversationId),
            message: simulateMessage.trim() || undefined,
          }),
        },
        'شبیه‌سازی پاسخ ناموفق بود.'
      );
      setSimulateResult(data?.draft_reply || '-');
    } catch (err) {
      const message = err instanceof Error ? err.message : 'شبیه‌سازی پاسخ ناموفق بود.';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const sections = result?.sections || {};
  const conversationState = sections.conversation_state_payload;
  const decisionEvents = Array.isArray(sections.decision_events)
    ? sections.decision_events
    : [];

  const handleClearState = async () => {
    setLoading(true);
    setError(null);
    setClearNotice(null);
    setPinNotice(null);
    try {
      if (!conversationId.trim()) {
        throw new Error('برای پاک‌کردن وضعیت باید conversation_id وارد شود.');
      }
      await fetchJson(
        `${API_URL}/admin/ai/clear_state?conversation_id=${conversationId.trim()}`,
        { method: 'POST' },
        'پاک‌کردن وضعیت ناموفق بود.'
      );
      await loadContext();
      setClearNotice('وضعیت گفتگو پاک شد.');
    } catch (err) {
      const message = err instanceof Error ? err.message : 'پاک‌کردن وضعیت ناموفق بود.';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const handlePinProduct = async () => {
    setLoading(true);
    setError(null);
    setClearNotice(null);
    setPinNotice(null);
    try {
      if (!conversationId.trim()) {
        throw new Error('برای پین محصول باید conversation_id وارد شود.');
      }
      if (!pinProductId.trim()) {
        throw new Error('شناسه محصول را وارد کنید.');
      }
      await fetchJson(
        `${API_URL}/admin/ai/pin_selected_product`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            conversation_id: Number(conversationId),
            product_id: Number(pinProductId),
          }),
        },
        'پین کردن محصول ناموفق بود.'
      );
      await loadContext();
      setPinNotice('محصول انتخاب‌شده ثبت شد.');
    } catch (err) {
      const message = err instanceof Error ? err.message : 'پین کردن محصول ناموفق بود.';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box sx={{ px: { xs: 2, md: 3 }, py: 2 }}>
      <Title title="کانتکست هوش مصنوعی" />
      <Stack spacing={2} sx={{ mb: 3 }}>
        <Typography variant="h4">کانتکست هوش مصنوعی</Typography>
        <Typography variant="body1" color="text.secondary">
          بررسی کنید که مدل برای هر کاربر چه اطلاعاتی دریافت می‌کند.
        </Typography>
      </Stack>

      <Card sx={{ mb: 2 }}>
        <CardContent>
          <Stack spacing={2}>
            <Typography variant="h6">انتخاب کاربر</Typography>
            <Stack direction={{ xs: 'column', md: 'row' }} spacing={2}>
              <TextField
                label="شناسه گفتگو (conversation_id)"
                value={conversationId}
                onChange={event => setConversationId(event.target.value)}
                fullWidth
              />
              <TextField
                label="شناسه کاربر (user_id)"
                value={userId}
                onChange={event => setUserId(event.target.value)}
                fullWidth
              />
              <TextField
                label="شناسه خارجی (external_id)"
                value={externalId}
                onChange={event => setExternalId(event.target.value)}
                fullWidth
              />
            </Stack>
            <Button variant="contained" onClick={loadContext} disabled={loading}>
              دریافت کانتکست
            </Button>
            <Button
              variant="outlined"
              color="warning"
              onClick={handleClearState}
              disabled={loading}
            >
              پاک‌کردن وضعیت گفتگو
            </Button>
            <Stack direction={{ xs: 'column', md: 'row' }} spacing={2}>
              <TextField
                label="شناسه محصول برای پین"
                value={pinProductId}
                onChange={event => setPinProductId(event.target.value)}
                fullWidth
              />
              <Button
                variant="outlined"
                color="primary"
                onClick={handlePinProduct}
                disabled={loading}
              >
                پین محصول انتخاب‌شده
              </Button>
            </Stack>
          </Stack>
        </CardContent>
      </Card>

      <Card sx={{ mb: 2 }}>
        <CardContent>
          <Stack spacing={2}>
            <Typography variant="h6">شبیه‌سازی پاسخ</Typography>
            <TextField
              label="پیام فرضی (اختیاری)"
              value={simulateMessage}
              onChange={event => setSimulateMessage(event.target.value)}
              fullWidth
            />
            <Button variant="outlined" onClick={handleSimulate} disabled={loading}>
              شبیه‌سازی پاسخ
            </Button>
            {simulateResult && (
              <Box
                component="pre"
                sx={{
                  whiteSpace: 'pre-wrap',
                  fontFamily: 'monospace',
                  fontSize: '0.85rem',
                  backgroundColor: 'rgba(0,0,0,0.04)',
                  padding: 2,
                  borderRadius: 1,
                  maxHeight: 240,
                  overflow: 'auto',
                }}
              >
                {simulateResult}
              </Box>
            )}
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

      {clearNotice && (
        <Card sx={{ mb: 2 }}>
          <CardContent>
            <Typography color="success.main">{clearNotice}</Typography>
          </CardContent>
        </Card>
      )}

      {pinNotice && (
        <Card sx={{ mb: 2 }}>
          <CardContent>
            <Typography color="success.main">{pinNotice}</Typography>
          </CardContent>
        </Card>
      )}

      {result && (
        <Stack spacing={2}>
          <Card>
            <CardContent>
              <Typography variant="h6">کاربر انتخاب‌شده</Typography>
              <Divider sx={{ my: 1 }} />
              <Typography variant="body2">
                شناسه: {result.user.id} | external_id: {result.user.external_id}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                نام کاربری: {result.user.username || '-'}
              </Typography>
            </CardContent>
          </Card>

          <Card>
            <CardContent>
              <Typography variant="h6">وضعیت گفتگو</Typography>
              <Divider sx={{ my: 1 }} />
              <Box
                component="pre"
                sx={{
                  whiteSpace: 'pre-wrap',
                  fontFamily: 'monospace',
                  fontSize: '0.85rem',
                  backgroundColor: 'rgba(0,0,0,0.04)',
                  padding: 2,
                  borderRadius: 1,
                  maxHeight: 240,
                  overflow: 'auto',
                }}
              >
                {conversationState
                  ? JSON.stringify(conversationState, null, 2)
                  : '-'}
              </Box>
            </CardContent>
          </Card>

          <Card>
            <CardContent>
              <Typography variant="h6">رویدادهای تصمیم</Typography>
              <Divider sx={{ my: 1 }} />
              <Stack spacing={1}>
                {decisionEvents.length === 0 && (
                  <Typography variant="body2" color="text.secondary">
                    رویدادی ثبت نشده است.
                  </Typography>
                )}
                {decisionEvents.map((event: any, index: number) => (
                  <Box
                    key={`${event.event_type || 'event'}-${index}`}
                    sx={{
                      backgroundColor: 'rgba(0,0,0,0.04)',
                      borderRadius: 1,
                      padding: 1.5,
                    }}
                  >
                    <Typography variant="subtitle2">
                      {event.event_type || 'event'}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {event.created_at || '-'}
                    </Typography>
                    <Box
                      component="pre"
                      sx={{
                        whiteSpace: 'pre-wrap',
                        fontFamily: 'monospace',
                        fontSize: '0.75rem',
                        margin: 0,
                      }}
                    >
                      {event.data ? JSON.stringify(event.data, null, 2) : '-'}
                    </Box>
                  </Box>
                ))}
              </Stack>
            </CardContent>
          </Card>

          <Card>
            <CardContent>
              <Typography variant="h6">کانتکست ترکیبی</Typography>
              <Divider sx={{ my: 1 }} />
              <Box
                component="pre"
                sx={{
                  whiteSpace: 'pre-wrap',
                  fontFamily: 'monospace',
                  fontSize: '0.85rem',
                  backgroundColor: 'rgba(0,0,0,0.04)',
                  padding: 2,
                  borderRadius: 1,
                  maxHeight: 320,
                  overflow: 'auto',
                }}
              >
                {result.context || '-'}
              </Box>
            </CardContent>
          </Card>

          <Card>
            <CardContent>
              <Typography variant="h6">بخش‌ها</Typography>
              <Divider sx={{ my: 1 }} />
              <Stack spacing={2}>
                {Object.entries(sections).map(([key, value]) => (
                  <Box key={key}>
                    <Typography variant="subtitle2">{key}</Typography>
                    <Box
                      component="pre"
                      sx={{
                        whiteSpace: 'pre-wrap',
                        fontFamily: 'monospace',
                        fontSize: '0.8rem',
                        backgroundColor: 'rgba(0,0,0,0.04)',
                        padding: 2,
                        borderRadius: 1,
                        maxHeight: 220,
                        overflow: 'auto',
                      }}
                    >
                      {typeof value === 'string'
                        ? value
                        : value
                          ? JSON.stringify(value, null, 2)
                          : '-'}
                    </Box>
                  </Box>
                ))}
              </Stack>
            </CardContent>
          </Card>
        </Stack>
      )}
    </Box>
  );
};
