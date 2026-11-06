import { ClosedCircleIcon } from '../icons/action-icons';
import { isLocationClosed, locationStatusLabel } from '../../lib/location-status';

export function ClosedLocationMark({ status }: { status: string }) {
  const label = locationStatusLabel(status);
  if (!isLocationClosed(status) || !label) {
    return null;
  }
  return (
    <span
      role='img'
      aria-label={label}
      title={label}
      className='ml-2 inline-flex text-red-600'
    >
      <ClosedCircleIcon className='h-4 w-4' />
    </span>
  );
}
