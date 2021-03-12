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
        # ref: aria2c -P -Z -c -x 5 -j 5 http://*.*/hls/*/seg-[1-254]-v1-a1.ts
        local m3u8url="$1"
        echo "Debug m3u8 url: $m3u8url"
        mkdir -p /tmp/gethls
        local id=$(uuidgen)
        echo "Debug session id: $id"
        echo "Making $id directory"
        mkdir -p /tmp/gethls/$id
        local m3u8name="$id"".m3u8"
        echo "Debug m3u8name: $m3u8name"
        curl --insecure -o "/tmp/gethls/$id/$m3u8name" $m3u8url
        tsfirst=(`cat "/tmp/gethls/$id/$m3u8name" | grep ts | sed -n '1p' | awk -F"-" '{print $2}'`)
        tslast=(`cat "/tmp/gethls/$id/$m3u8name" | grep ts | sed -n '$p' | awk -F"-" '{print $2}'`)
        echo $tsfirst
        echo $tslast
        m3u8name=(`echo $m3u8url |  awk -F"/" '{print $NF}'`)
        # sottrarre m3u8name a $m3u8url
        match=$m3u8name
        echo "Debug match string: $m3u8name"

        replace=seg-[$tsfirst-$tslast]-v1-a1.ts
        echo "Debug: replace string: $replace"

        echo "Debug: the string: $m3u8url"

        newUrl=${m3u8url/$match/$replace}
        echo "Debug: newUrl string: $newUrl"
        # concatenare a m3u8url seg-[$tsfirst-$tslast]-v1-a1.ts
        # ffmpeg -allowed_extensions ALL -i index.m3u8 -c:v copy -c:a copy ../pppd-369.mkv
        aria2c -P -Z -c -x 5 -j 5 -d /tmp/gethls/$id $newUrl
        ffmpeg -allowed_extensions ALL -i /tmp/gethls/$id/$m3u8name -c:v copy -c:a copy /tmp/gethls/$id.mkv

}

