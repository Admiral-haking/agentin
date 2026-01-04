import {
  Datagrid,
  FunctionField,
  List,
  TextField,
  TextInput,
} from 'react-admin';
import { Chip } from '@mui/material';
import { ResourceTitle } from '../components/ResourceTitle';
import { TehranDateField } from '../components/TehranDateField';

const ConversationFilters = [
  <TextInput key="user_id" source="user_id" label="شناسه کاربر" />,
  <TextInput key="username" source="username" label="نام کاربری" />,
  <TextInput key="status" source="status" label="وضعیت" />,
  <TextInput key="from" label="از (ISO)" source="from" />,
  <TextInput key="to" label="تا (ISO)" source="to" />,
];

export const ConversationList = () => (
  <List
    filters={ConversationFilters}
    sort={{ field: 'last_user_message_at', order: 'DESC' }}
    title={
      <ResourceTitle
        title="گفتگوها"
        subtitle="این‌باکس یکپارچه کاربران اینستاگرام."
        tag="زنده"
      />
    }
  >
    <Datagrid>
      <TextField source="id" label="شناسه" />
      <TextField source="user_id" label="کاربر" />
      <TextField source="user_external_id" label="شناسه اینستاگرام" />
      <TextField source="username" label="نام کاربری" />
      <FunctionField
        label="VIP"
        render={(record: any) =>
          record?.is_vip ? <Chip label="VIP" color="secondary" size="small" /> : '-'
        }
      />
      <TextField source="vip_score" label="امتیاز VIP" />
      <TextField source="status" label="وضعیت" />
      <TehranDateField source="last_user_message_at" label="آخرین پیام کاربر" showTime />
      <TehranDateField source="last_bot_message_at" label="آخرین پاسخ ربات" showTime />
      <TehranDateField source="created_at" label="شروع گفتگو" showTime />
    </Datagrid>
  </List>
);
