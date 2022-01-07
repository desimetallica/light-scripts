#!/bin/bash

logger -i "`date`: sending email!"

from="backupServer"
subject="Failure!"
recipients="mail@mail.com"

/usr/sbin/sendmail "$recipients" << EOF
subject:$subject
from:$from
to:$recipients

This is an error message.
 Something goes wrong with the backup at `date`

EOF

echo "email sent!"
logger -i "`date`: email sent!"
