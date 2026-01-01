import {
  Datagrid,
  List,
  TextField,
  TextInput,
} from 'react-admin';
import { TehranDateField } from '../components/TehranDateField';
import { ResourceTitle } from '../components/ResourceTitle';

const MessageFilters = [
  <TextInput key="conversation_id" source="conversation_id" label="شناسه گفتگو" />,
  <TextInput key="role" source="role" label="نقش" />,
  <TextInput key="type" source="type" label="نوع" />,
  <TextInput key="contains" source="contains" label="جستجوی متن" />,
  <TextInput key="from" label="از (ISO)" source="from" />,
  <TextInput key="to" label="تا (ISO)" source="to" />,
];

export const MessageList = () => (
  <List
    filters={MessageFilters}
    title={
      <ResourceTitle
        title="پیام‌ها"
        subtitle="همه پیام‌های ورودی و خروجی همراه با زمان."
      />
    }
  >
    <Datagrid>
      <TextField source="id" label="شناسه" />
      <TextField source="conversation_id" label="گفتگو" />
      <TextField source="role" label="نقش" />
      <TextField source="type" label="نوع" />
      <TextField source="content_text" label="متن" />
      <TehranDateField source="created_at" label="زمان" showTime />
    </Datagrid>
  </List>
);
