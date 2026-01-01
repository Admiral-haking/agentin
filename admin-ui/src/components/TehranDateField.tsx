import { DateField, type DateFieldProps } from 'react-admin';

const tehranOptions: Intl.DateTimeFormatOptions = {
  timeZone: 'Asia/Tehran',
};

export const TehranDateField = (props: DateFieldProps) => (
  <DateField {...props} options={tehranOptions} />
);
