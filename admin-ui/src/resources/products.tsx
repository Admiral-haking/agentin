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
} from 'react-admin';
import { ResourceTitle } from '../components/ResourceTitle';

const ProductFilters = [
  <TextInput key="q" label="جستجو" source="q" alwaysOn />, // title
  <TextInput key="category" source="category" label="دسته" />,
  <BooleanInput key="in_stock" source="in_stock" label="موجود" />,
];

export const ProductList = () => (
  <List
    filters={ProductFilters}
    title={
      <ResourceTitle
        title="محصولات"
        subtitle="اطلاعات محصول برای قیمت‌گذاری و موجودی."
        tag="کاتالوگ"
      />
    }
  >
    <Datagrid rowClick="edit">
      <TextField source="id" label="شناسه" />
      <TextField source="title" label="عنوان" />
      <TextField source="category" label="دسته" />
      <TextField source="price_range" label="بازه قیمت" />
      <BooleanField source="in_stock" label="موجود" />
    </Datagrid>
  </List>
);

export const ProductCreate = () => (
  <Create>
    <SimpleForm>
      <TextInput source="title" label="عنوان" fullWidth />
      <TextInput source="category" label="دسته" />
      <TextInput source="price_range" label="بازه قیمت" />
      <TextInput source="sizes" label="سایزها" helperText="با کاما جدا کنید" />
      <TextInput source="colors" label="رنگ‌ها" helperText="با کاما جدا کنید" />
      <TextInput source="images" label="تصاویر" helperText="با کاما جدا کنید" />
      <TextInput source="link" label="لینک محصول" fullWidth />
      <BooleanInput source="in_stock" label="موجود" />
    </SimpleForm>
  </Create>
);

export const ProductEdit = () => (
  <Edit>
    <SimpleForm>
      <TextInput source="title" label="عنوان" fullWidth />
      <TextInput source="category" label="دسته" />
      <TextInput source="price_range" label="بازه قیمت" />
      <TextInput source="sizes" label="سایزها" helperText="با کاما جدا کنید" />
      <TextInput source="colors" label="رنگ‌ها" helperText="با کاما جدا کنید" />
      <TextInput source="images" label="تصاویر" helperText="با کاما جدا کنید" />
      <TextInput source="link" label="لینک محصول" fullWidth />
      <BooleanInput source="in_stock" label="موجود" />
    </SimpleForm>
  </Edit>
);
