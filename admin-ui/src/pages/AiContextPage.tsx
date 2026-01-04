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
import { fetchWithAuth } from '../authProvider';

const DEFAULT_API_URL = import.meta.env.DEV
  ? 'http://localhost:8000'
  : 'https://api.teamcore.ir';
const API_URL = import.meta.env.VITE_API_URL || DEFAULT_API_URL;

type AiContextResponse = {
  user: { id: number; external_id: string; username?: string | null };
  context: string;
  sections: Record<string, string | null>;
};

export const AiContextPage = () => {
  const [userId, setUserId] = useState('');
  const [externalId, setExternalId] = useState('');
  const [result, setResult] = useState<AiContextResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadContext = async () => {
    setLoading(true);
    setError(null);
    try {
      const query = new URLSearchParams();
      if (userId.trim()) {
        query.set('user_id', userId.trim());
      } else if (externalId.trim()) {
        query.set('external_id', externalId.trim());
      } else {
        throw new Error('شناسه کاربر یا external_id را وارد کنید.');
      }
      const response = await fetchWithAuth(`${API_URL}/admin/ai/context?${query}`);
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data?.detail || 'دریافت کانتکست ناموفق بود.');
      }
      setResult(data);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'دریافت کانتکست ناموفق بود.';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const sections = result?.sections || {};

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
                      {value || '-'}
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
