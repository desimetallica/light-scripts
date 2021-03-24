function getlink()
{
        local link="$1"
        echo "Debug link: $link"
        local id=$(uuidgen)
        echo "Debug session id: $id"
        /usr/bin/tmux new-session -s "$id" -d "aria2c -d /default/location --seed-time=0 \"$@\" 2>&1 | tee \"/tmp/$id\""
}

function gethls()
{
        local id=$(uuidgen)
        mkdir -p /tmp/gethls
        mkdir -p /tmp/gethls/$id
        touch /tmp/gethls/$id/$id.log
        LOG_FILE=/tmp/gethls/$id/$id.log

        #exec 3>&1 1>>${LOG_FILE} 2>&1

        # ref: aria2c -P -Z -c -x 5 -j 5 http://*.*/hls/*/seg-[1-254]-v1-a1.ts
        local m3u8url="$1"
        echo " `date` DEBUG: m3u8 url: $m3u8url " >> $LOG_FILE
        echo " `date` DEBUG: session id: $id" >> $LOG_FILE

        local m3u8name="$id"".m3u8"
        echo " `date` DEBUG: m3u8name: $m3u8name" >> $LOG_FILE

        echo " `date` INFO:  curl --insecure -o /tmp/gethls/$id/$m3u8name $m3u8url " >> $LOG_FILE
        curl --insecure -o "/tmp/gethls/$id/$m3u8name" $m3u8url

        tsfirst=(`cat "/tmp/gethls/$id/$m3u8name" | grep ts | sed -n '1p' | awk -F"-" '{print $2}'`)
        tslast=(`cat "/tmp/gethls/$id/$m3u8name" | grep ts | sed -n '$p' | awk -F"-" '{print $2}'`)
        echo " `date` DEBUG: tsfirst: $tsfirst " >> $LOG_FILE
        echo " `date` DEBUG: tslast $tslast " >> $LOG_FILE

        match=(`echo $m3u8url |  awk -F"/" '{print $NF}'`)
        # sottrarre m3u8name a $m3u8url
        echo " `date` DEBUG: match string: $match" >> $LOG_FILE

        replace=seg-[$tsfirst-$tslast]-v1-a1.ts
        echo " `date` DEBUG: replace string: $replace" >> $LOG_FILE

        echo " `date` DEBUG: the string: $m3u8url" >> $LOG_FILE

        newUrl=${m3u8url/$match/$replace}
        echo " `date` DEBUG: newUrl string: $newUrl" >> $LOG_FILE
        # concatenare a m3u8url seg-[$tsfirst-$tslast]-v1-a1.ts
        # ffmpeg -allowed_extensions ALL -i index.m3u8 -c:v copy -c:a copy ../pppd-369.mkv
        echo " `date` INFO: aria2c -P -Z -c -x 5 -j 5 -d /tmp/gethls/$id $newUrl " >> $LOG_FILE
        aria2c -P -Z -c -x 5 -j 5 -d /tmp/gethls/$id $newUrl

        echo " `date` INFO: ffmpeg -allowed_extensions ALL -i /tmp/gethls/$id/$m3u8name -c:v copy -c:a copy /tmp/gethls/$id.mkv " >> $LOG_FILE
        ffmpeg -allowed_extensions ALL -i /tmp/gethls/$id/$m3u8name -c:v copy -c:a copy /tmp/gethls/$id.mkv
}
