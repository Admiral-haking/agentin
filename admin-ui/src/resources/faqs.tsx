import {
  BooleanField,
  BooleanInput,
  Create,
  Datagrid,
  Edit,
  List,
  TextField,
  TextInput,
  SimpleForm,
  required,
} from 'react-admin';
import { ResourceTitle } from '../components/ResourceTitle';

const FaqFilters = [
  <TextInput key="q" label="جستجو" source="q" alwaysOn />, // question/answer
  <TextInput key="category" source="category" label="دسته" />,
  <BooleanInput key="verified" source="verified" label="تایید شده" />,
];

export const FaqList = () => (
  <List
    filters={FaqFilters}
    title={
      <ResourceTitle
        title="سوالات متداول"
        subtitle="پاسخ‌های تاییدشده برای هوش مصنوعی و قوانین."
        tag="دانش"
      />
    }
  >
    <Datagrid rowClick="edit">
      <TextField source="id" label="شناسه" />
      <TextField source="question" label="سوال" />
      <BooleanField source="verified" label="تایید" />
      <TextField source="category" label="دسته" />
    </Datagrid>
  </List>
);

export const FaqCreate = () => (
  <Create>
    <SimpleForm>
      <TextInput source="question" label="سوال" fullWidth validate={required()} />
      <TextInput source="answer" label="پاسخ" multiline fullWidth validate={required()} />
      <TextInput source="tags" label="برچسب‌ها" helperText="با کاما جدا کنید" />
      <TextInput source="category" label="دسته" />
      <BooleanInput source="verified" label="تایید شده" />
    </SimpleForm>
  </Create>
);

export const FaqEdit = () => (
  <Edit>
    <SimpleForm>
      <TextInput source="question" label="سوال" fullWidth validate={required()} />
      <TextInput source="answer" label="پاسخ" multiline fullWidth validate={required()} />
      <TextInput source="tags" label="برچسب‌ها" helperText="با کاما جدا کنید" />
      <TextInput source="category" label="دسته" />
      <BooleanInput source="verified" label="تایید شده" />
    </SimpleForm>
  </Edit>
);
