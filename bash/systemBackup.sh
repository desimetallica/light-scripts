#!/bin/sh

#vars
recipients="mail@mail.com"
from="Automatic Backup System"
backupName="systemBackup"
# Setting this, so the repo does not need to be given on the commandline:
export BORG_REPO=/media/Backup/$backupName

# See the section "Passphrase notes" for more infos.
export BORG_PASSPHRASE=''
export BORG_RELOCATED_REPO_ACCESS_IS_OK=yes

# some helpers and error handling:
info() { printf "\n%s %s\n\n" "$( date )" "$*" >&2; }
trap 'echo $( date ) Backup interrupted >&2; exit 2' INT TERM

logger -i "$backupName Starting backup"

# Backup the most important directories into an archive named after
# the machine this script is currently running on:

backupOut=$(borg create                         \
          --verbose                       \
          --filter AME                    \
          --list                          \
          --stats                         \
          --show-rc                       \
          --compression lz4               \
          --exclude-caches                \
          --exclude '/home/*/.cache/*'    \
          --exclude '/var/cache/*'        \
          --exclude '/var/tmp/*'          \
          --exclude '/var/lock/*'         \
          --exclude '/dev/*'              \
          --exclude '/sys/*'              \
          --exclude '/mnt/*'              \
          --exclude '/proc/*'             \
          --exclude '/tmp/*'              \
          --exclude '/lost+found/*'       \
          --exclude '/media/*'            \
                                          \
          ::"{hostname}-{now}"            \
          /etc                            \
          /home                           \
          /root                           \
          /var                            \
          /opt                            \
          /usr                            \
          /srv 2>&1)

backup_exit=$?

logger -i "$backupName Pruning repository"

# Use the `prune` subcommand to maintain 7 daily, 4 weekly and 6 monthly
# archives of THIS machine. The '{hostname}-' prefix is very important to
# limit prune's operation to this machine's archives and not apply to
# other machines' archives also:

pruneOut=$(borg prune                          \
    --list                          \
    --prefix "{hostname}-"          \
    --show-rc                       \
    --keep-daily    7               \
    --keep-weekly   4               \
    --keep-monthly  6 2>&1)

prune_exit=$?

# use highest exit code as global exit code
global_exit=$(( backup_exit > prune_exit ? backup_exit : prune_exit ))

if [ ${global_exit} -eq 0 ]; then
    logger -i "$backupName and Prune finished successfully"
elif [ ${global_exit} -eq 1 ]; then
     logger -i "[WARNING] $backupName and/or Prune finished with warnings"
     logger -i "[WARNING] $backupName borg create comand error is: $backupOut"
     logger -i "[WARNING] $backupName prune comand error is: $pruneOut"

    /usr/sbin/sendmail "$recipients" <<- EOF
subject:$backupName finished with warnings
from:$from
to:$recipients

This is an WARNING message.
Something went wrong with the $backupName `date`

Check the following waning messages:
borg create cmd:
$backupOut

prune cmd:
$pruneOut

EOF

else
    logger -i "[ERROR] $backupName and/or Prune finished with errors"
    logger -i "[ERROR] $backupName borg create comand error is: $backupOut"
    logger -i "[ERROR] $backupName prune comand error is: $pruneOut"

    /usr/sbin/sendmail "$recipients" <<- EOF
subject:$backupName finished with errors
from:$from
to:$recipients

This is an ERROR message.
Something went wrong with the $backupName `date`

Check the following waning messages:
borg create cmd:
$backupOut

prune cmd:
$pruneOut
EOF
fi

exit ${global_exit}

