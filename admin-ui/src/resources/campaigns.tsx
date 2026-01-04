import {
  BooleanField,
  BooleanInput,
  Create,
  Datagrid,
  DateField,
  DateTimeInput,
  Edit,
  List,
  NumberField,
  NumberInput,
  TextField,
  TextInput,
  SimpleForm,
  required,
} from 'react-admin';
import { ResourceTitle } from '../components/ResourceTitle';

const CampaignFilters = [
  <TextInput key="q" label="جستجو" source="q" alwaysOn />, // title/body
  <BooleanInput key="active" label="فعال" source="active" />,
];

export const CampaignList = () => (
  <List
    filters={CampaignFilters}
    sort={{ field: 'updated_at', order: 'DESC' }}
    title={
      <ResourceTitle
        title="کمپین‌ها"
        subtitle="کمپین‌ها و پروموشن‌های زمان‌بندی‌شده."
        tag="ارسال"
      />
    }
  >
    <Datagrid rowClick="edit">
      <TextField source="id" label="شناسه" />
      <TextField source="title" label="عنوان" />
      <BooleanField source="active" label="فعال" />
      <NumberField source="priority" label="اولویت" />
      <DateField source="start_at" label="شروع" />
      <DateField source="end_at" label="پایان" />
      <DateField source="updated_at" label="بروزرسانی" />
    </Datagrid>
  </List>
);

export const CampaignCreate = () => (
  <Create>
    <SimpleForm>
      <TextInput source="title" label="عنوان" fullWidth validate={required()} />
      <TextInput source="body" label="متن پیام" multiline fullWidth validate={required()} />
      <TextInput source="discount_code" label="کد تخفیف" />
      <TextInput source="link" label="لینک کمپین" fullWidth />
      <DateTimeInput source="start_at" label="زمان شروع" />
      <DateTimeInput source="end_at" label="زمان پایان" />
      <BooleanInput source="active" label="فعال" />
      <NumberInput source="priority" label="اولویت" />
    </SimpleForm>
  </Create>
);

export const CampaignEdit = () => (
  <Edit>
    <SimpleForm>
      <TextInput source="title" label="عنوان" fullWidth validate={required()} />
      <TextInput source="body" label="متن پیام" multiline fullWidth validate={required()} />
      <TextInput source="discount_code" label="کد تخفیف" />
      <TextInput source="link" label="لینک کمپین" fullWidth />
      <DateTimeInput source="start_at" label="زمان شروع" />
      <DateTimeInput source="end_at" label="زمان پایان" />
      <BooleanInput source="active" label="فعال" />
      <NumberInput source="priority" label="اولویت" />
    </SimpleForm>
  </Edit>
);
