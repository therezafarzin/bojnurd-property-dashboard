#!/bin/bash
cd "$(dirname "$0")"
printf "تمام تاریخچه و دیتابیس پاک شود؟ (yes/no): "
read answer
if [ "$answer" = "yes" ]; then
  rm -f data/market.db data/market.db-shm data/market.db-wal
  echo "دیتابیس پاک شد."
else
  echo "لغو شد."
fi
