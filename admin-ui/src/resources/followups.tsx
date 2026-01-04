import {
  Datagrid,
  DateTimeInput,
  Edit,
  FunctionField,
  List,
  SelectInput,
  SimpleForm,
  TextField,
  TextInput,
} from 'react-admin';
import { Chip } from '@mui/material';
import { ResourceTitle } from '../components/ResourceTitle';
import { TehranDateField } from '../components/TehranDateField';

const statusChoices = [
  { id: 'scheduled', name: 'زمان‌بندی شده' },
  { id: 'sent', name: 'ارسال شده' },
  { id: 'cancelled', name: 'لغو شده' },
  { id: 'skipped', name: 'رد شده' },
  { id: 'failed', name: 'ناموفق' },
];

const FollowupFilters = [
  <TextInput key="user_id" source="user_id" label="شناسه کاربر" />,
  <TextInput key="conversation_id" source="conversation_id" label="شناسه گفتگو" />,
  <SelectInput key="status" source="status" label="وضعیت" choices={statusChoices} />,
];

const renderStatus = (record: any) => {
  const value = record?.status || 'scheduled';
  const meta =
    value === 'sent'
      ? { label: 'ارسال شده', color: 'success' as const }
    : value === 'failed'
      ? { label: 'ناموفق', color: 'error' as const }
        : value === 'cancelled'
          ? { label: 'لغو شده', color: 'default' as const }
          : value === 'skipped'
            ? { label: 'رد شده', color: 'default' as const }
          : { label: 'زمان‌بندی شده', color: 'warning' as const };
  return <Chip label={meta.label} color={meta.color} size="small" />;
};

const formatJson = (value: any) =>
  value ? JSON.stringify(value, null, 2) : '';

const parseJson = (value: string) => {
  if (!value) return null;
  try {
    return JSON.parse(value);
  } catch (error) {
    return null;
  }
};

const validateJson = (value: string) => {
  if (!value) return undefined;
  try {
    JSON.parse(value);
    return undefined;
  } catch (error) {
    return 'JSON نامعتبر است';
  }
};

export const FollowupList = () => (
  <List
    filters={FollowupFilters}
    sort={{ field: 'scheduled_for', order: 'DESC' }}
    title={
      <ResourceTitle
        title="پیگیری‌های خودکار"
        subtitle="یادآوری‌های زمان‌بندی شده برای کاربران."
        tag="پیگیری"
      />
    }
  >
    <Datagrid rowClick="edit" bulkActionButtons={false}>
      <TextField source="id" label="شناسه" />
      <TextField source="user_id" label="کاربر" />
      <TextField source="conversation_id" label="گفتگو" />
      <FunctionField label="وضعیت" render={renderStatus} />
      <TehranDateField source="scheduled_for" label="زمان ارسال" showTime />
      <TehranDateField source="sent_at" label="ارسال شد" showTime />
      <TextField source="reason" label="دلیل" />
      <FunctionField
        label="Payload"
        render={(record: any) =>
          record?.payload ? JSON.stringify(record.payload) : '-'
        }
      />
      <TehranDateField source="updated_at" label="بروزرسانی" showTime />
    </Datagrid>
  </List>
);

export const FollowupEdit = () => (
  <Edit
    title={
      <ResourceTitle
        title="ویرایش پیگیری"
        subtitle="زمان‌بندی و وضعیت یادآوری را اصلاح کنید."
      />
    }
  >
    <SimpleForm>
      <TextInput source="id" label="شناسه" disabled />
      <TextInput source="user_id" label="شناسه کاربر" disabled />
      <TextInput source="conversation_id" label="شناسه گفتگو" disabled />
      <SelectInput source="status" label="وضعیت" choices={statusChoices} />
      <DateTimeInput source="scheduled_for" label="زمان ارسال" />
      <TextInput source="reason" label="دلیل" fullWidth />
      <TextInput
        source="payload"
        label="Payload"
        fullWidth
        multiline
        format={formatJson}
        parse={parseJson}
        validate={validateJson}
        helperText="JSON معتبر وارد کنید."
      />
    </SimpleForm>
  </Edit>
);
