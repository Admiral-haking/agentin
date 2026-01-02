import {
  Create,
  Datagrid,
  DateField,
  DateInput,
  Edit,
  FunctionField,
  List,
  NumberField,
  NumberInput,
  SelectInput,
  SimpleForm,
  TextField,
  TextInput,
  TopToolbar,
  UrlField,
  useNotify,
  useRefresh,
} from 'react-admin';
import { Button, Chip, Stack, Tabs, Tab } from '@mui/material';
import SyncRoundedIcon from '@mui/icons-material/SyncRounded';
import { Link, useLocation } from 'react-router-dom';
import { ResourceTitle } from '../components/ResourceTitle';
import { fetchWithAuth } from '../authProvider';

const DEFAULT_API_URL = import.meta.env.DEV
  ? 'http://localhost:8000'
  : 'https://api.teamcore.ir';
const API_URL = import.meta.env.VITE_API_URL || DEFAULT_API_URL;

const ProductFilters = [
  <TextInput key="q" label="جستجو" source="q" alwaysOn />,
  <SelectInput
    key="availability"
    source="availability"
    label="وضعیت موجودی"
    choices={[
      { id: 'instock', name: 'موجود' },
      { id: 'outofstock', name: 'ناموجود' },
      { id: 'unknown', name: 'نامشخص' },
    ]}
  />,
  <NumberInput key="min_price" source="min_price" label="حداقل قیمت" />,
  <NumberInput key="max_price" source="max_price" label="حداکثر قیمت" />,
  <DateInput key="updated_from" source="updated_from" label="از تاریخ بروزرسانی" />,
  <DateInput key="updated_to" source="updated_to" label="تا تاریخ بروزرسانی" />,
];

const ProductsHeader = () => {
  const location = useLocation();
  const tabValue = location.pathname.includes('product-sync-runs') ? 1 : 0;
  return (
    <Stack spacing={2}>
      <ResourceTitle
        title="محصولات"
        subtitle="کاتالوگ همگام با فروشگاه و توروب."
        tag="کاتالوگ"
      />
      <Tabs value={tabValue} textColor="primary" indicatorColor="primary">
        <Tab label="محصولات" component={Link} to="/products" />
        <Tab label="گزارش همگام‌سازی" component={Link} to="/product-sync-runs" />
      </Tabs>
    </Stack>
  );
};

const ProductListActions = () => {
  const notify = useNotify();
  const refresh = useRefresh();
  const handleSync = async () => {
    try {
      const response = await fetchWithAuth(`${API_URL}/admin/products/sync`, {
        method: 'POST',
      });
      if (!response.ok) {
        throw new Error('sync failed');
      }
      notify('همگام‌سازی شروع شد.', { type: 'info' });
      refresh();
    } catch (error) {
      notify('خطا در شروع همگام‌سازی', { type: 'warning' });
    }
  };

  return (
    <TopToolbar>
      <Button
        onClick={handleSync}
        variant="contained"
        color="primary"
        startIcon={<SyncRoundedIcon />}
      >
        همگام‌سازی محصولات
      </Button>
    </TopToolbar>
  );
};

const availabilityMeta = (value?: string) => {
  switch (value) {
    case 'instock':
      return { label: 'موجود', color: 'success' as const };
    case 'outofstock':
      return { label: 'ناموجود', color: 'error' as const };
    default:
      return { label: 'نامشخص', color: 'warning' as const };
  }
};

export const ProductList = () => (
  <List
    filters={ProductFilters}
    title={<ProductsHeader />}
    sort={{ field: 'updated_at', order: 'DESC' }}
    actions={<ProductListActions />}
  >
    <Datagrid rowClick="edit">
      <TextField source="id" label="شناسه" />
      <FunctionField
        label="عنوان"
        render={(record: any) => record.title || record.slug || '-'}
      />
      <TextField source="slug" label="اسلاگ" />
      <NumberField source="price" label="قیمت" />
      <NumberField source="old_price" label="قیمت قبل" />
      <FunctionField
        label="موجودی"
        render={(record: any) => {
          const meta = availabilityMeta(record.availability);
          return <Chip label={meta.label} color={meta.color} size="small" />;
        }}
      />
      <DateField source="updated_at" label="بروزرسانی" showTime />
      <DateField source="lastmod" label="آخرین تغییر سایت" showTime />
      <UrlField source="page_url" label="لینک" />
    </Datagrid>
  </List>
);

export const ProductCreate = () => (
  <Create>
    <SimpleForm>
      <TextInput source="page_url" label="لینک محصول" fullWidth />
      <TextInput source="title" label="عنوان" fullWidth />
      <TextInput source="slug" label="اسلاگ" />
      <TextInput source="product_id" label="شناسه توروب" />
      <SelectInput
        source="availability"
        label="موجودی"
        choices={[
          { id: 'instock', name: 'موجود' },
          { id: 'outofstock', name: 'ناموجود' },
          { id: 'unknown', name: 'نامشخص' },
        ]}
      />
      <NumberInput source="price" label="قیمت" />
      <NumberInput source="old_price" label="قیمت قبل" />
      <TextInput source="description" label="توضیحات" fullWidth multiline />
      <TextInput source="images" label="تصاویر" helperText="با کاما جدا کنید" />
    </SimpleForm>
  </Create>
);

export const ProductEdit = () => (
  <Edit>
    <SimpleForm>
      <TextInput source="page_url" label="لینک محصول" fullWidth />
      <TextInput source="title" label="عنوان" fullWidth />
      <TextInput source="slug" label="اسلاگ" />
      <TextInput source="product_id" label="شناسه توروب" />
      <SelectInput
        source="availability"
        label="موجودی"
        choices={[
          { id: 'instock', name: 'موجود' },
          { id: 'outofstock', name: 'ناموجود' },
          { id: 'unknown', name: 'نامشخص' },
        ]}
      />
      <NumberInput source="price" label="قیمت" />
      <NumberInput source="old_price" label="قیمت قبل" />
      <TextInput source="description" label="توضیحات" fullWidth multiline />
      <TextInput source="images" label="تصاویر" helperText="با کاما جدا کنید" />
    </SimpleForm>
  </Edit>
);
