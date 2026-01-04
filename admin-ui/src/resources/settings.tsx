import {
  BooleanInput,
  Datagrid,
  Edit,
  List,
  NumberInput,
  SelectInput,
  SimpleForm,
  TextField,
  TextInput,
} from 'react-admin';
import { Card, CardContent, Stack, Typography } from '@mui/material';
import { ResourceTitle } from '../components/ResourceTitle';

const modeChoices = [
  { id: 'hybrid', name: 'هیبرید (پیشنهادی)' },
  { id: 'openai', name: 'فقط OpenAI' },
  { id: 'deepseek', name: 'فقط DeepSeek' },
];

export const SettingsList = () => (
  <List
    title={
      <ResourceTitle
        title="تنظیمات هوش مصنوعی"
        subtitle="کنترل مسیر مدل‌ها، سقف پاسخ و پرامپت سیستم."
        tag="مدیریت"
      />
    }
  >
    <Datagrid rowClick="edit">
      <TextField source="id" label="شناسه" />
      <TextField source="ai_mode" label="حالت هوش" />
      <TextField source="max_output_chars" label="حداکثر پاسخ" />
      <TextField source="max_history_messages" label="تاریخچه" />
      <TextField source="active" label="فعال" />
      <TextField source="followup_enabled" label="پیگیری فعال" />
    </Datagrid>
  </List>
);

export const SettingsEdit = () => (
  <Edit
    title={
      <ResourceTitle
        title="مرکز کنترل هوش"
        subtitle="تنظیم انتخاب مدل، استراتژی پرامپت و پاسخ جایگزین."
        tag="سیستم"
      />
    }
  >
    <SimpleForm>
      <Stack spacing={2}>
        <Card>
          <CardContent>
            <Stack spacing={1.5}>
              <Typography variant="h6">مسیر مدل‌ها</Typography>
              <Typography variant="body2" color="text.secondary">
                نحوه تولید پاسخ را انتخاب کنید. حالت هیبرید به صورت خودکار بهترین مدل را انتخاب می‌کند.
              </Typography>
              <SelectInput
                source="ai_mode"
                label="حالت هوش"
                choices={modeChoices}
                helperText="هیبرید برای توازن کیفیت و هزینه پیشنهاد می‌شود."
              />
              <Stack direction={{ xs: 'column', md: 'row' }} spacing={2}>
                <NumberInput
                  source="max_output_chars"
                  label="حداکثر طول پاسخ"
                  helperText="سقف تعداد کاراکتر پاسخ."
                />
                <NumberInput
                  source="max_history_messages"
                  label="عمق تاریخچه"
                  helperText="تعداد پیام‌های اخیر در زمینه."
                />
              </Stack>
            </Stack>
          </CardContent>
        </Card>

        <Card>
          <CardContent>
            <Stack spacing={1.5}>
              <Typography variant="h6">استراتژی پرامپت</Typography>
              <Typography variant="body2" color="text.secondary">
                پرامپت سیستم لحن و سیاست‌ها را تعیین می‌کند. از متن جایگزین برای پاسخ امن استفاده کنید.
              </Typography>
              <TextInput
                source="system_prompt"
                label="پرامپت سیستم"
                multiline
                fullWidth
                helperText="دستور اصلی که به مدل داده می‌شود."
              />
              <TextInput
                source="admin_notes"
                label="یادداشت ادمین"
                multiline
                fullWidth
                helperText="نکات ویژه برای مدل (فقط مدیریت)."
              />
              <TextInput
                source="fallback_text"
                label="پاسخ جایگزین"
                multiline
                fullWidth
                helperText="وقتی خروجی مدل خالی یا ناامن است."
              />
            </Stack>
          </CardContent>
        </Card>

        <Card>
          <CardContent>
            <Stack spacing={1.5}>
              <Typography variant="h6">پیگیری خودکار</Typography>
              <Typography variant="body2" color="text.secondary">
                ارسال یک یادآوری امن پس از قطع گفتگوهای فروش.
              </Typography>
              <BooleanInput source="followup_enabled" label="پیگیری فعال" />
              <NumberInput
                source="followup_delay_hours"
                label="تاخیر (ساعت)"
                helperText="مثال: 6 تا 24 ساعت"
              />
              <TextInput
                source="followup_message"
                label="متن پیگیری"
                multiline
                fullWidth
                helperText="متن کوتاه یادآوری (اختیاری)"
              />
            </Stack>
          </CardContent>
        </Card>

        <Card>
          <CardContent>
            <Stack spacing={1}>
              <Typography variant="h6">فعال‌سازی</Typography>
              <Typography variant="body2" color="text.secondary">
                برای فعال/غیرفعال کردن تنظیمات فعلی استفاده کنید.
              </Typography>
              <BooleanInput source="active" label="تنظیمات فعال" />
            </Stack>
          </CardContent>
        </Card>
      </Stack>
    </SimpleForm>
  </Edit>
);
