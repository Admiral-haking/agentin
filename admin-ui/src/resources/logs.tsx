import {
  Datagrid,
  List,
  TextField,
  TextInput,
} from 'react-admin';
import { TehranDateField } from '../components/TehranDateField';
import { ResourceTitle } from '../components/ResourceTitle';

const LogFilters = [
  <TextInput key="level" source="level" label="سطح" />,
  <TextInput key="event_type" source="event_type" label="رویداد" />,
  <TextInput key="contains" source="contains" label="جستجو" />,
  <TextInput key="from" label="از (ISO)" source="from" />,
  <TextInput key="to" label="تا (ISO)" source="to" />,
];

export const LogList = () => (
  <List
    filters={LogFilters}
    title={
      <ResourceTitle
        title="لاگ‌های سیستم"
        subtitle="ورودی وبهوک، ارسال‌های خروجی و خطاهای سیستم."
        tag="عیب‌یابی"
      />
    }
  >
    <Datagrid>
      <TextField source="id" label="شناسه" />
      <TextField source="level" label="سطح" />
      <TextField source="event_type" label="نوع رویداد" />
      <TextField source="message" label="پیام" />
      <TehranDateField source="created_at" label="زمان" showTime />
    </Datagrid>
  </List>
);
