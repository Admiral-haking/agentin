import { useState } from 'react';
import {
  Box,
  Button,
  Divider,
  InputAdornment,
  Paper,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import MailOutlineRoundedIcon from '@mui/icons-material/MailOutlineRounded';
import LockRoundedIcon from '@mui/icons-material/LockRounded';
import { useLogin, useNotify } from 'react-admin';
import { InlineAlert } from '../components/InlineAlert';

export const LoginPage = () => {
  const login = useLogin();
  const notify = useNotify();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({ username: '', password: '' });

  const handleChange =
    (field: 'username' | 'password') =>
      (event: React.ChangeEvent<HTMLInputElement>) => {
        setForm(prev => ({ ...prev, [field]: event.target.value }));
      };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await login(form);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'نام کاربری یا رمز عبور اشتباه است.';
      setError(message);
      notify(message, { type: 'warning' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box
      sx={{
        minHeight: '100vh',
        display: 'grid',
        placeItems: 'center',
        px: 2,
        py: 4,
      }}
    >
      <Paper
        sx={{
          width: '100%',
          maxWidth: 460,
          p: { xs: 2.5, sm: 4 },
          borderRadius: 4,
          backdropFilter: 'blur(12px)',
          background:
            'linear-gradient(150deg, rgba(255,255,255,0.96) 0%, rgba(255,255,255,0.9) 100%)',
        }}
      >
        <Stack spacing={3}>
          <Stack spacing={1}>
            <Typography variant="h4">ورود به پنل مدیریت</Typography>
            <Typography variant="body2" color="text.secondary">
              برای مدیریت گفتگوها، داده‌ها و تنظیمات هوش مصنوعی وارد شوید.
            </Typography>
          </Stack>

          <Divider sx={{ opacity: 0.6 }} />

          <Box component="form" onSubmit={handleSubmit}>
            <Stack spacing={2}>
              <TextField
                label="ایمیل یا نام کاربری"
                value={form.username}
                onChange={handleChange('username')}
                fullWidth
                autoFocus
                InputProps={{
                  startAdornment: (
                    <InputAdornment position="start">
                      <MailOutlineRoundedIcon fontSize="small" />
                    </InputAdornment>
                  ),
                }}
              />
              <TextField
                label="رمز عبور"
                type="password"
                value={form.password}
                onChange={handleChange('password')}
                fullWidth
                InputProps={{
                  startAdornment: (
                    <InputAdornment position="start">
                      <LockRoundedIcon fontSize="small" />
                    </InputAdornment>
                  ),
                }}
              />
              {error && <InlineAlert message={error} title="ورود ناموفق" />}
              <Button
                type="submit"
                variant="contained"
                size="large"
                disabled={loading || !form.username || !form.password}
              >
                {loading ? 'در حال ورود...' : 'ورود'}
              </Button>
            </Stack>
          </Box>

          <Typography variant="caption" color="text.secondary" sx={{ textAlign: 'center' }}>
            اگر مشکل ورود دارید، سطح دسترسی یا تنظیمات API را بررسی کنید.
          </Typography>
        </Stack>
      </Paper>
    </Box>
  );
};
