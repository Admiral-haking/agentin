import { useState } from 'react';
import {
  Box,
  Button,
  Chip,
  Divider,
  FormControl,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import SendRoundedIcon from '@mui/icons-material/SendRounded';
import PersonSearchRoundedIcon from '@mui/icons-material/PersonSearchRounded';
import { Title } from 'react-admin';
import { fetchJson } from '../utils/api';
import { InlineAlert } from '../components/InlineAlert';

const DEFAULT_API_URL = import.meta.env.DEV
  ? 'http://localhost:8000'
  : 'https://api.teamcore.ir';
const API_URL = import.meta.env.VITE_API_URL || DEFAULT_API_URL;

type SendType =
  | 'text'
  | 'photo'
  | 'video'
  | 'audio'
  | 'button'
  | 'quick_reply'
  | 'generic_template';

type LookupType = 'username' | 'follow-status' | 'follow-count';

const parseJsonList = (value: string, label: string) => {
  if (!value.trim()) {
    return [];
  }
  let parsed: unknown;
  try {
    parsed = JSON.parse(value);
  } catch {
    throw new Error(`${label} باید JSON معتبر باشد.`);
  }
  if (!Array.isArray(parsed)) {
    throw new Error(`${label} باید آرایه باشد.`);
  }
  return parsed;
};

export const DirectamConsole = () => {
  const [receiverId, setReceiverId] = useState('');
  const [sendType, setSendType] = useState<SendType>('text');
  const [text, setText] = useState('');
  const [imageUrl, setImageUrl] = useState('');
  const [videoUrl, setVideoUrl] = useState('');
  const [audioUrl, setAudioUrl] = useState('');
  const [buttonsJson, setButtonsJson] = useState(
    '[{"type":"web_url","title":"مشاهده سایت","url":"https://example.com"}]'
  );
  const [quickRepliesJson, setQuickRepliesJson] = useState(
    '[{"title":"گزینه ۱","payload":"option_1"},{"title":"گزینه ۲","payload":"option_2"}]'
  );
  const [elementsJson, setElementsJson] = useState(
    '[{"title":"کارت اول","subtitle":"توضیح کوتاه","image_url":"https://example.com/image.jpg","buttons":[{"type":"postback","title":"انتخاب","payload":"choose_1"}]}]'
  );
  const [lookupUserId, setLookupUserId] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sendResult, setSendResult] = useState<Record<string, unknown> | null>(null);
  const [lookupResult, setLookupResult] = useState<Record<string, unknown> | null>(null);

  const buildPayload = () => {
    const trimmedReceiver = receiverId.trim();
    if (!trimmedReceiver) {
      throw new Error('شناسه گیرنده (receiver_id) را وارد کنید.');
    }

    const payload: Record<string, unknown> = {
      receiver_id: trimmedReceiver,
      type: sendType,
    };

    if (sendType === 'text') {
      const trimmedText = text.trim();
      if (!trimmedText) {
        throw new Error('متن پیام الزامی است.');
      }
      payload.text = trimmedText;
    }

    if (sendType === 'photo') {
      if (!imageUrl.trim()) {
        throw new Error('آدرس تصویر الزامی است.');
      }
      payload.image_url = imageUrl.trim();
    }

    if (sendType === 'video') {
      if (!videoUrl.trim()) {
        throw new Error('آدرس ویدیو الزامی است.');
      }
      payload.video_url = videoUrl.trim();
    }

    if (sendType === 'audio') {
      if (!audioUrl.trim()) {
        throw new Error('آدرس فایل صوتی الزامی است.');
      }
      payload.audio_url = audioUrl.trim();
    }

    if (sendType === 'button') {
      const trimmedText = text.trim();
      if (!trimmedText) {
        throw new Error('متن پیام برای دکمه‌ها الزامی است.');
      }
      payload.text = trimmedText;
      payload.buttons = parseJsonList(buttonsJson, 'لیست دکمه‌ها');
    }

    if (sendType === 'quick_reply') {
      const trimmedText = text.trim();
      if (!trimmedText) {
        throw new Error('متن پیام برای پاسخ سریع الزامی است.');
      }
      payload.text = trimmedText;
      payload.quick_replies = parseJsonList(quickRepliesJson, 'لیست پاسخ سریع');
    }

    if (sendType === 'generic_template') {
      payload.elements = parseJsonList(elementsJson, 'اسلایدها');
    }

    return payload;
  };

  const handleSend = async () => {
    setLoading(true);
    setError(null);
    setSendResult(null);
    try {
      const payload = buildPayload();
      const data = await fetchJson(
        `${API_URL}/admin/directam/send`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        },
        'ارسال پیام ناموفق بود.'
      );
      setSendResult(data || {});
    } catch (err) {
      const message = err instanceof Error ? err.message : 'ارسال پیام ناموفق بود.';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const handleLookup = async (type: LookupType) => {
    setLoading(true);
    setError(null);
    setLookupResult(null);
    try {
      const userId = lookupUserId.trim();
      if (!userId) {
        throw new Error('شناسه کاربر را وارد کنید.');
      }
      const data = await fetchJson(
        `${API_URL}/admin/directam/instagram-user/${type}`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ user_id: userId }),
        },
        'دریافت اطلاعات ناموفق بود.'
      );
      setLookupResult(data || {});
    } catch (err) {
      const message = err instanceof Error ? err.message : 'دریافت اطلاعات ناموفق بود.';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box sx={{ px: { xs: 2, md: 3 }, py: 2 }}>
      <Title title="کنسول دایرکتم" />
      <Stack spacing={2} sx={{ mb: 3 }}>
        <Typography variant="h4">کنسول دایرکتم</Typography>
        <Typography variant="body1" color="text.secondary">
          همه قابلیت‌های ارسال و دریافت اطلاعات کاربر از همینجا قابل استفاده است.
        </Typography>
      </Stack>

      <Stack spacing={2}>
        <Paper sx={{ p: { xs: 2, md: 3 } }}>
          <Stack spacing={2}>
            <Stack direction="row" alignItems="center" spacing={1}>
              <SendRoundedIcon color="primary" />
              <Typography variant="h6">ارسال پیام</Typography>
              <Chip label="قانون ۲۴ ساعته فعال" size="small" color="warning" />
            </Stack>
            <Divider />
            <Stack spacing={2}>
              <TextField
                label="شناسه گیرنده (receiver_id)"
                value={receiverId}
                onChange={event => setReceiverId(event.target.value)}
                fullWidth
                sx={{
                  '& .MuiInputBase-input': {
                    direction: 'ltr',
                    textAlign: 'left',
                  },
                }}
              />
              <FormControl fullWidth>
                <InputLabel id="directam-type-label">نوع ارسال</InputLabel>
                <Select
                  labelId="directam-type-label"
                  label="نوع ارسال"
                  value={sendType}
                  onChange={event => setSendType(event.target.value as SendType)}
                >
                  <MenuItem value="text">متن</MenuItem>
                  <MenuItem value="photo">تصویر</MenuItem>
                  <MenuItem value="video">ویدیو</MenuItem>
                  <MenuItem value="audio">صوت</MenuItem>
                  <MenuItem value="button">متن + دکمه</MenuItem>
                  <MenuItem value="quick_reply">متن + پاسخ سریع</MenuItem>
                  <MenuItem value="generic_template">ویترین (Generic Template)</MenuItem>
                </Select>
              </FormControl>

              {(sendType === 'text' || sendType === 'button' || sendType === 'quick_reply') && (
                <TextField
                  label="متن پیام"
                  value={text}
                  onChange={event => setText(event.target.value)}
                  multiline
                  minRows={3}
                  fullWidth
                  sx={{
                    '& .MuiInputBase-input': {
                      direction: 'rtl',
                      textAlign: 'right',
                      lineHeight: 1.8,
                    },
                  }}
                />
              )}

              {sendType === 'photo' && (
                <TextField
                  label="آدرس تصویر (image_url)"
                  value={imageUrl}
                  onChange={event => setImageUrl(event.target.value)}
                  fullWidth
                  sx={{
                    '& .MuiInputBase-input': {
                      direction: 'ltr',
                      textAlign: 'left',
                    },
                  }}
                />
              )}

              {sendType === 'video' && (
                <TextField
                  label="آدرس ویدیو (video_url)"
                  value={videoUrl}
                  onChange={event => setVideoUrl(event.target.value)}
                  fullWidth
                  sx={{
                    '& .MuiInputBase-input': {
                      direction: 'ltr',
                      textAlign: 'left',
                    },
                  }}
                />
              )}

              {sendType === 'audio' && (
                <TextField
                  label="آدرس فایل صوتی (audio_url)"
                  value={audioUrl}
                  onChange={event => setAudioUrl(event.target.value)}
                  fullWidth
                  sx={{
                    '& .MuiInputBase-input': {
                      direction: 'ltr',
                      textAlign: 'left',
                    },
                  }}
                />
              )}

              {sendType === 'button' && (
                <TextField
                  label="لیست دکمه‌ها (JSON)"
                  value={buttonsJson}
                  onChange={event => setButtonsJson(event.target.value)}
                  multiline
                  minRows={4}
                  helperText='مثال: [{"type":"web_url","title":"مشاهده سایت","url":"https://example.com"}]'
                  fullWidth
                  sx={{
                    '& .MuiInputBase-input': {
                      direction: 'ltr',
                      textAlign: 'left',
                      fontFamily: 'monospace',
                    },
                  }}
                />
              )}

              {sendType === 'quick_reply' && (
                <TextField
                  label="لیست پاسخ سریع (JSON)"
                  value={quickRepliesJson}
                  onChange={event => setQuickRepliesJson(event.target.value)}
                  multiline
                  minRows={4}
                  helperText='مثال: [{"title":"گزینه ۱","payload":"option_1"}]'
                  fullWidth
                  sx={{
                    '& .MuiInputBase-input': {
                      direction: 'ltr',
                      textAlign: 'left',
                      fontFamily: 'monospace',
                    },
                  }}
                />
              )}

              {sendType === 'generic_template' && (
                <TextField
                  label="اسلایدهای ویترین (JSON)"
                  value={elementsJson}
                  onChange={event => setElementsJson(event.target.value)}
                  multiline
                  minRows={5}
                  helperText="هر اسلاید باید title داشته باشد. حداکثر ۱۰ اسلاید."
                  fullWidth
                  sx={{
                    '& .MuiInputBase-input': {
                      direction: 'ltr',
                      textAlign: 'left',
                      fontFamily: 'monospace',
                    },
                  }}
                />
              )}

              <Button
                variant="contained"
                color="primary"
                onClick={handleSend}
                disabled={loading}
              >
                ارسال
              </Button>
              {sendResult && (
                <Paper variant="outlined" sx={{ p: 1.5 }}>
                  <Typography variant="subtitle2">پاسخ سرویس:</Typography>
                  <pre style={{ margin: 0, direction: 'ltr' }}>
                    {JSON.stringify(sendResult, null, 2)}
                  </pre>
                </Paper>
              )}
            </Stack>
          </Stack>
        </Paper>

        <Paper sx={{ p: { xs: 2, md: 3 } }}>
          <Stack spacing={2}>
            <Stack direction="row" alignItems="center" spacing={1}>
              <PersonSearchRoundedIcon color="primary" />
              <Typography variant="h6">اطلاعات کاربر اینستاگرام</Typography>
            </Stack>
            <Divider />
            <TextField
              label="شناسه کاربر (user_id)"
              value={lookupUserId}
              onChange={event => setLookupUserId(event.target.value)}
              fullWidth
              sx={{
                '& .MuiInputBase-input': {
                  direction: 'ltr',
                  textAlign: 'left',
                },
              }}
            />
            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1}>
              <Button
                variant="outlined"
                onClick={() => handleLookup('username')}
                disabled={loading}
              >
                نام کاربری
              </Button>
              <Button
                variant="outlined"
                onClick={() => handleLookup('follow-status')}
                disabled={loading}
              >
                وضعیت فالو
              </Button>
              <Button
                variant="outlined"
                onClick={() => handleLookup('follow-count')}
                disabled={loading}
              >
                تعداد فالوورها
              </Button>
            </Stack>
            {lookupResult && (
              <Paper variant="outlined" sx={{ p: 1.5 }}>
                <Typography variant="subtitle2">نتیجه:</Typography>
                <pre style={{ margin: 0, direction: 'ltr' }}>
                  {JSON.stringify(lookupResult, null, 2)}
                </pre>
              </Paper>
            )}
          </Stack>
        </Paper>

        {error && <InlineAlert title="خطای کنسول" message={error} />}
      </Stack>
    </Box>
  );
};
