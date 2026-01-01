import {
  Datagrid,
  List,
  TextField,
  TextInput,
} from 'react-admin';
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
      <TextField source="status" label="وضعیت" />
      <TehranDateField source="last_user_message_at" label="آخرین پیام کاربر" showTime />
      <TehranDateField source="last_bot_message_at" label="آخرین پاسخ ربات" showTime />
      <TehranDateField source="created_at" label="شروع گفتگو" showTime />
    </Datagrid>
  </List>
);
