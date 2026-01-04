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
  required,
} from 'react-admin';
import { Button, Chip, Stack, Tabs, Tab } from '@mui/material';
import SyncRoundedIcon from '@mui/icons-material/SyncRounded';
import { Link, useLocation } from 'react-router-dom';
import { ResourceTitle } from '../components/ResourceTitle';
import { fetchJson } from '../utils/api';

const DEFAULT_API_URL = import.meta.env.DEV
  ? 'http://localhost:8000'
  : 'https://api.teamcore.ir';
const API_URL = import.meta.env.VITE_API_URL || DEFAULT_API_URL;

const proxyImageUrl = (value?: string | null) => {
  if (!value) return value;
  if (value.startsWith(API_URL)) return value;
  return `${API_URL}/media-proxy?url=${encodeURIComponent(value)}`;
};

const ProductFilters = [
  <TextInput key="q" label="جستجو" source="q" alwaysOn />,
  <TextInput key="product_id" label="مدل/شناسه توروب" source="product_id" />,
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
  <SelectInput
    key="has_price"
    source="has_price"
    label="قیمت دارد"
    choices={[
      { id: 'true', name: 'دارد' },
      { id: 'false', name: 'ندارد' },
    ]}
  />,
  <SelectInput
    key="has_old_price"
    source="has_old_price"
    label="قیمت قبل دارد"
    choices={[
      { id: 'true', name: 'دارد' },
      { id: 'false', name: 'ندارد' },
    ]}
  />,
  <SelectInput
    key="has_product_id"
    source="has_product_id"
    label="مدل دارد"
    choices={[
      { id: 'true', name: 'دارد' },
      { id: 'false', name: 'ندارد' },
    ]}
  />,
  <SelectInput
    key="has_images"
    source="has_images"
    label="تصویر دارد"
    choices={[
      { id: 'true', name: 'دارد' },
      { id: 'false', name: 'ندارد' },
    ]}
  />,
  <SelectInput
    key="source"
    source="source"
    label="منبع"
    choices={[
      { id: 'torob', name: 'توروب' },
      { id: 'sitemap', name: 'سایت' },
      { id: 'scraped', name: 'اسکرپ' },
    ]}
  />,
  <DateInput key="updated_from" source="updated_from" label="از تاریخ بروزرسانی" />,
  <DateInput key="updated_to" source="updated_to" label="تا تاریخ بروزرسانی" />,
  <DateInput key="lastmod_from" source="lastmod_from" label="از آخرین تغییر سایت" />,
  <DateInput key="lastmod_to" source="lastmod_to" label="تا آخرین تغییر سایت" />,
];

const formatImages = (value: any) => {
  if (Array.isArray(value)) {
    return value.join(', ');
  }
  return value || '';
};

const parseImages = (value: string) =>
  value
    ? value
        .split(',')
        .map(item => item.trim())
        .filter(Boolean)
    : [];

const renderProductImage = (record: any) => {
  const images = Array.isArray(record?.images) ? record.images : [];
  const url = images.length ? proxyImageUrl(images[0]) : null;
  if (!url) return '-';
  return (
    <img
      src={url}
      alt={record?.title || record?.slug || 'product'}
      style={{ width: 48, height: 48, objectFit: 'cover', borderRadius: 6 }}
    />
  );
};

const renderImageCount = (record: any) => {
  const images = Array.isArray(record?.images)
    ? record.images
    : typeof record?.images === 'string'
      ? record.images.split(',').map((item: string) => item.trim()).filter(Boolean)
      : [];
  return images.length ? `${images.length} تصویر` : '-';
};

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
      await fetchJson(
        `${API_URL}/admin/products/sync`,
        { method: 'POST' },
        'sync failed'
      );
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
      <FunctionField label="تصویر" render={renderProductImage} />
      <FunctionField
        label="عنوان"
        render={(record: any) => record.title || record.slug || '-'}
      />
      <TextField source="product_id" label="مدل/توروب" />
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
      <FunctionField label="تصاویر" render={renderImageCount} />
      <UrlField source="page_url" label="لینک" />
    </Datagrid>
  </List>
);

export const ProductCreate = () => (
  <Create>
    <SimpleForm>
      <TextInput source="page_url" label="لینک محصول" fullWidth validate={required()} />
      <TextInput source="title" label="عنوان" fullWidth />
      <TextInput source="slug" label="اسلاگ" />
      <TextInput source="product_id" label="مدل/شناسه توروب" />
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
      <TextInput
        source="images"
        label="تصاویر"
        helperText="URLها را با کاما جدا کنید"
        format={formatImages}
        parse={parseImages}
        fullWidth
      />
    </SimpleForm>
  </Create>
);

export const ProductEdit = () => (
  <Edit>
    <SimpleForm>
      <TextInput source="page_url" label="لینک محصول" fullWidth />
      <TextInput source="title" label="عنوان" fullWidth />
      <TextInput source="slug" label="اسلاگ" />
      <TextInput source="product_id" label="مدل/شناسه توروب" />
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
      <TextInput
        source="images"
        label="تصاویر"
        helperText="URLها را با کاما جدا کنید"
        format={formatImages}
        parse={parseImages}
        fullWidth
      />
    </SimpleForm>
  </Edit>
);
