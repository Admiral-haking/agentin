import {
  Datagrid,
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
  { id: 'open', name: 'باز' },
  { id: 'pending', name: 'در انتظار' },
  { id: 'resolved', name: 'حل‌شده' },
];

const TicketFilters = [
  <TextInput key="user_id" source="user_id" label="شناسه کاربر" />,
  <TextInput key="conversation_id" source="conversation_id" label="شناسه گفتگو" />,
  <TextInput key="external_id" source="external_id" label="شناسه اینستاگرام" />,
  <SelectInput key="status" source="status" label="وضعیت" choices={statusChoices} />,
];

const renderStatus = (record: any) => {
  const value = record?.status || 'open';
  const meta =
    value === 'resolved'
      ? { label: 'حل‌شده', color: 'success' as const }
      : value === 'pending'
        ? { label: 'در انتظار', color: 'warning' as const }
        : { label: 'باز', color: 'error' as const };
  return <Chip label={meta.label} color={meta.color} size="small" />;
};

export const TicketList = () => (
  <List
    filters={TicketFilters}
    sort={{ field: 'updated_at', order: 'DESC' }}
    title={
      <ResourceTitle
        title="تیکت‌های پشتیبانی"
        subtitle="درخواست‌های بحرانی و پیام‌های شکایت کاربران."
        tag="پشتیبانی"
      />
    }
  >
    <Datagrid rowClick="edit" bulkActionButtons={false}>
      <TextField source="id" label="شناسه" />
      <TextField source="user_id" label="کاربر" />
      <TextField source="conversation_id" label="گفتگو" />
      <FunctionField label="وضعیت" render={renderStatus} />
      <TextField source="summary" label="خلاصه" />
      <TextField source="last_message" label="آخرین پیام" />
      <TehranDateField source="created_at" label="ایجاد" showTime />
      <TehranDateField source="updated_at" label="بروزرسانی" showTime />
    </Datagrid>
  </List>
);

export const TicketEdit = () => (
  <Edit
    title={
      <ResourceTitle
        title="ویرایش تیکت"
        subtitle="وضعیت و خلاصه را بروزرسانی کنید."
      />
    }
  >
    <SimpleForm>
      <TextInput source="id" label="شناسه" disabled />
      <TextInput source="user_id" label="شناسه کاربر" disabled />
      <TextInput source="conversation_id" label="شناسه گفتگو" disabled />
      <SelectInput source="status" label="وضعیت" choices={statusChoices} />
      <TextInput source="summary" label="خلاصه" fullWidth multiline />
      <TextInput source="last_message" label="آخرین پیام" fullWidth multiline />
    </SimpleForm>
  </Edit>
);
