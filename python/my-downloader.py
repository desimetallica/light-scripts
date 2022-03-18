#!/usr/bin/env python3

from email.message import EmailMessage
from ast import Str
from typing import Dict, List
from pathlib import Path
import smtplib
import time
import uuid
import fire
import libtorrent as lt
import logging
import os 
import socket
import configparser

LOG_FORMAT = ("%(asctime)s [%(levelname)s]: %(message)s in %(pathname)s:%(lineno)d")
LOG_FORMAT_STATUS = ("%(asctime)s [%(levelname)s]: %(message)s")
LOG_LEVEL = logging.DEBUG

# GLOBAL_HOME = os.environ(["HOME"])
APPLICATION_NAME = "my-downloader"

DEFAULT_LOG_FOLDER_NAME = "downloader-log"
DEFAULT_DOWNLOAD_FOLDER_NAME = "torrent-download"
DEFAULT_LISTEN_PORT = 6881
DEFAULT_LISTEN_INTERFACE = "0.0.0.0"
DEFAULT_MAX_DOWNLOAD_RATE = 0
DEFAULT_MAX_UPLOAD_RATE = 0
DEFAULT_OUTGOING_INTERFACE = ""
DEFAULT_EMAIL_USER = "email@gmail.com"
DEFAULT_EMAIL_PWD = "P4SSW0RD!"

DEFAULT_CONFIG_PATH = os.environ["HOME"] + "/.config/" + APPLICATION_NAME
DEFAULT_LOG_FOLDER = "/tmp/" + DEFAULT_LOG_FOLDER_NAME
DEFAULT_DOWNLOAD_FOLDER = os.environ["HOME"] + "/" + DEFAULT_DOWNLOAD_FOLDER_NAME

def folderCheckCreate(path: str) -> bool:
    try:
        Path(path).mkdir(parents=True, exist_ok=True)
        return True
    except BaseException as err:
        print(f"Unexptected {err=}, {type(err)=}")

def add_suffix(val):
    prefix = ['B', 'kB', 'MB', 'GB', 'TB']
    for i in range(len(prefix)):
        if abs(val) < 1000:
            if i == 0:
                return '%5.3g%s' % (val, prefix[i])
            else:
                return '%4.3g%s' % (val, prefix[i])
        val /= 1000

    return '%6.3gPB' % val

def write_line(console, line):
    console.write(line)

def progress_bar(progress, width):
    assert(progress <= 1)
    progress_chars = int(progress * width + 0.5)
    return progress_chars * '#' + (width - progress_chars) * '-'

def print_peer_info(console, peers):

    out = (' down    (total )   up     (total )'
           '  q  r flags  block progress  client\n')

    for p in peers:

        out += '%s/s ' % add_suffix(p.down_speed)
        out += '(%s) ' % add_suffix(p.total_download)
        out += '%s/s ' % add_suffix(p.up_speed)
        out += '(%s) ' % add_suffix(p.total_upload)
        out += '%2d ' % p.download_queue_length
        out += '%2d ' % p.upload_queue_length

        out += 'I' if p.flags & lt.peer_info.interesting else '.'
        out += 'C' if p.flags & lt.peer_info.choked else '.'
        out += 'i' if p.flags & lt.peer_info.remote_interested else '.'
        out += 'c' if p.flags & lt.peer_info.remote_choked else '.'
        out += 'e' if p.flags & lt.peer_info.supports_extensions else '.'
        out += 'l' if p.flags & lt.peer_info.local_connection else 'r'
        out += ' '

        if p.downloading_piece_index >= 0:
            assert(p.downloading_progress <= p.downloading_total)
            out += progress_bar(float(p.downloading_progress) /
                                p.downloading_total, 15)
        else:
            out += progress_bar(0, 15)
        out += ' '

        if p.flags & lt.peer_info.handshake:
            id = 'waiting for handshake'
        elif p.flags & lt.peer_info.connecting:
            id = 'connecting to peer'
        else:
            id = p.client

        out += '%s\n' % id[:10]

    write_line(console, out)

def print_download_queue(console, download_queue):

    out = ""

    for e in download_queue:
        out += '%4d: [' % e['piece_index']
        for b in e['blocks']:
            s = b['state']
            if s == 3:
                out += '#'
            elif s == 2:
                out += '='
            elif s == 1:
                out += '-'
            else:
                out += ' '
        out += ']\n'

    write_line(console, out)

def add_torrent(ses, filename, savePath):
    atp = lt.add_torrent_params()
    if filename.startswith('magnet:'):
        atp = lt.parse_magnet_uri(filename)
    else:
        ti = lt.torrent_info(filename)
        resume_file = os.path.join(savePath, ti.name() + '.fastresume')
        try:
            atp = lt.read_resume_data(open(resume_file, 'rb').read())
        except Exception as e:
            print('failed to open resume file "%s": %s' % (resume_file, e))
        atp.ti = ti

    atp.save_path = savePath
    atp.storage_mode = lt.storage_mode_t.storage_mode_sparse
    atp.flags |= lt.torrent_flags.duplicate_is_error \
        | lt.torrent_flags.auto_managed \
        | lt.torrent_flags.duplicate_is_error
    return ses.add_torrent(atp)


class Downloader(object):
    """
    Downloader is download class for Torrent it has some useful for torrents downloading

    Downloader class comes with some useful COMMANDS:

        downloadMagnet --magnet_link=MAGNET_LINK download a torrent with provided MAGNET_LINK 

    :param save_path: location of default storing torrents 
    :type save_path: str
    :param log_path: location of default log messages of application 
    :type log_path: str
    :param listen_interface: setup listen interface  
    :type log_path: str
    :param outgoing_interface: setup outgoing interface  
    :type log_path: str
    :param listen_port: setup listen port of torrent client
    :type log_path: int
    :param max_download_rate: setup max download rate limit in KB/s
    :type log_path: int
    :param max_upload_rate: setup max upload rate limit in KB/s
    :type log_path: int

    """
    _save_path: str
    _log_path: str
    _listen_interface: str
    _listen_port: int
    _max_download_rate: int
    _max_upload_rate: int
    _outgoing_interface: str
    _messaging_logger: logging.Logger
    _config_path: str
    _UUID: uuid.UUID
    _sender_email: str
    _sender_email_pwd: str

    def __init__(self, config_path=DEFAULT_CONFIG_PATH, 
                    save_path=DEFAULT_DOWNLOAD_FOLDER, 
                    log_path=DEFAULT_LOG_FOLDER,
                    listen_interface=DEFAULT_LISTEN_INTERFACE,
                    listen_port=DEFAULT_LISTEN_PORT,
                    max_download_rate=DEFAULT_MAX_DOWNLOAD_RATE,
                    max_upload_rate=DEFAULT_MAX_UPLOAD_RATE,
                    outgoing_interface=DEFAULT_OUTGOING_INTERFACE) -> None:
        try:

            pLog = Path(log_path)
            
            if log_path == DEFAULT_LOG_FOLDER: 
                pLog.mkdir(parents=True, exist_ok=True)
                self._log_path = str(pLog)
            else: 
                pLog = pLog / DEFAULT_LOG_FOLDER_NAME
                pLog.mkdir(parents=True, exist_ok=True)
                self._log_path = str(pLog)

            self._UUID = uuid.uuid4()
            self.initLogger(self._UUID)
            self._messaging_logger.info("Initializing application")

            pSave = Path(save_path)
            pConf = Path(config_path)
            
            if config_path == DEFAULT_CONFIG_PATH:
                pConf.mkdir(parents=True, exist_ok=True)
                if os.path.isfile(pConf / "config.ini"): #if file exist already read it
                    self._messaging_logger.info("Initializing email user and pwd from config file")
                    config = configparser.ConfigParser()
                    config.read_file(open(str(pConf) + "/config.ini"))
                    if config['DEFAULT']["SenderEmail"]:
                        self._sender_email =  config['DEFAULT']["SenderEmail"]
                    if config['DEFAULT']["SenderEmailPassword"]:
                        self._sender_email_pwd =  config['DEFAULT']["SenderEmailPassword"]
                else: #if not exist initialize and write it down
                    self._messaging_logger.info("Config file not found using default email user and pwd")
                    config = configparser.ConfigParser()
                    config.read(str(pConf) + "/config.ini")
                    config['DEFAULT'] = {'SenderEmail': DEFAULT_EMAIL_USER, 'SenderEmailPassword': DEFAULT_EMAIL_PWD}
                    self._sender_email =  config['DEFAULT']["SenderEmail"]
                    self._sender_email_pwd =  config['DEFAULT']["SenderEmailPassword"]
                    # config.read_file(open(str(pConf) + "/config.ini"))
                    with open(str(pConf / "config.ini"), "w") as configFile:
                        config.write(configFile)

            if save_path == DEFAULT_DOWNLOAD_FOLDER: 
                self._messaging_logger.warning("Using default torrent save path: " + save_path)
                pSave.mkdir(parents=True, exist_ok=True)
                self._save_path = str(pSave)
            else: 
                pSave = pSave / DEFAULT_DOWNLOAD_FOLDER_NAME
                pSave.mkdir(parents=True, exist_ok=True)
                self._save_path = str(pSave)
            
            if listen_port < 0 or listen_port > 65525:
                self._messaging_logger.warning("Listen port value invalid using default value: " + str(self._listen_port))
                self._listen_port = 6881
            else: self._listen_port = listen_port
            if max_upload_rate <= 0:
                self._max_upload_rate = -1
            else:
                self._max_upload_rate = max_upload_rate * 1000
            if max_download_rate <= 0:
                self._max_download_rate = -1
            else:
                self._max_download_rate = max_download_rate * 1000

            # validate ips
            if listen_interface == DEFAULT_LISTEN_INTERFACE:
                self._messaging_logger.warning("Using default listen interface value: " + DEFAULT_LISTEN_INTERFACE)
                self._listen_interface = listen_interface
            else:
                socket.inet_aton(listen_interface)
                self._listen_interface = listen_interface
            
            if outgoing_interface == DEFAULT_OUTGOING_INTERFACE:
                self._outgoing_interface = outgoing_interface
            else:
                socket.inet_aton(outgoing_interface)
                self._outgoing_interface = outgoing_interface
        except BaseException as err:
            self._messaging_logger.error(f"Unexpected error {err=}, {type(err)=}")
            print(f"Unexptected {err=}, {type(err)=}")

    def initLogger(self, downloadUUID):
        messaging_logger = logging.getLogger("downloader.messaging")
        messaging_logger.setLevel(LOG_LEVEL)
        messaging_logger_file_handler = logging.FileHandler(self._log_path + "/" + str(downloadUUID) + ".log")
        messaging_logger_file_handler.setLevel(LOG_LEVEL)
        messaging_logger_file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
        # messaging_logger_file_handler.mode = "a"
        messaging_logger.addHandler(messaging_logger_file_handler)
        self._messaging_logger = messaging_logger

    def sendMail(self, msg: EmailMessage) -> None:

        # gmail_user = DEFAULT_EMAIL_USER
        # gmail_password = 'daoyzimwuvbslqkw'

        try:
            server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
            server.ehlo()
            server.login(self._sender_email, self._sender_email_pwd)
            server.sendmail(self._sender_email, msg["To"], msg.as_string())
            server.close()

            self._messaging_logger.info("Email sent correctly to: " + msg["To"])
        except BaseException as err:
            self._messaging_logger.error(f"Unexpected error {err=}, {type(err)=}")
            print(f"Unexptected {err=}, {type(err)=}")

    def downloadMagnet(self, magnet_link: str):
        """
        Download a torrent using a magnet link provided
        :param magnet_link: a valid magnet link 
        :type magnet_link: str
        """
        # print(self._save_path, self._log_path)
        # downloadUUID = uuid.uuid4()
        # messaging_logger = logging.getLogger("downloader.messaging")
        # messaging_logger.setLevel(LOG_LEVEL)
        # messaging_logger_file_handler = logging.FileHandler(self._log_path + "/" + str(downloadUUID) + ".log")
        # messaging_logger_file_handler.setLevel(LOG_LEVEL)
        # messaging_logger_file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
        # messaging_logger_file_handler.mode = "a"
        # messaging_logger.addHandler(messaging_logger_file_handler)

        # status_logger = logging.getLogger("downloader.status")
        # status_logger.setLevel(LOG_LEVEL)
        # status_file_handler = logging.FileHandler(self._log_path + "/" + str(downloadUUID) + ".status")
        # status_file_handler.setLevel(LOG_LEVEL)
        # status_file_handler.setFormatter(logging.Formatter(LOG_FORMAT_STATUS))
        # status_file_handler.mode = "w"
        # status_logger.addHandler(status_file_handler)

        self._messaging_logger.info("Download folder provided: " + self._save_path)
        self._messaging_logger.info("Magnet link provided " + magnet_link)
        
        settings = {
            'user_agent': 'python_client/' + lt.__version__,
            'listen_interfaces': '%s:%d' % (self._listen_interface, self._listen_port),
            # 'download_rate_limit': int(self._max_download_rate),
            # 'upload_rate_limit': int(self._max_upload_rate),
            'alert_mask': lt.alert.category_t.all_categories,
            'outgoing_interfaces': self._outgoing_interface,
        }

        self._messaging_logger.info("libTorrent settings: " + str(settings))
        self._messaging_logger.info("Starting libTorrent session")
        ses = lt.session(settings)
        
        h = add_torrent(ses, magnet_link, self._save_path)
        h.set_download_limit(self._max_download_rate)
        h.set_upload_limit(self._max_upload_rate)
        h.resume

        self._messaging_logger.info("Downloading metadata...")
        while (not h.has_metadata):
            time.sleep(1)
        self._messaging_logger.info("Starting torrent download")
        while (h.status().state != lt.torrent_status.seeding):
            s = h.status()
            state_str = ['queued', 'checking', 'downloading metadata', 'downloading', 'finished', 'seeding', 'allocating']
            
            out = ""
            out += '%.2f%% complete (down: %.1f kb/s up: %.1f kB/s peers: %d) %s' % (s.progress * 100, s.download_rate / 1000, s.upload_rate / 1000, s.num_peers, state_str[s.state])
            out += '\n'
            if s.state != lt.torrent_status.seeding:
                state_str = ['queued', 'checking', 'downloading metadata',
                             'downloading', 'finished', 'seeding',
                             '', 'checking fastresume']
                out += state_str[s.state] + ' '

                out += '%5.4f%% ' % (s.progress * 100)
                out += progress_bar(s.progress, 49)
                out += '\n'

                out += 'total downloaded: %d Bytes\n' % s.total_done
                out += 'peers: %d seeds: %d distributed copies: %d\n' % \
                    (s.num_peers, s.num_seeds, s.distributed_copies)
                out += '\n'

            out += 'download: %s/s (%s) ' \
                % (add_suffix(s.download_rate), add_suffix(s.total_download))
            out += 'upload: %s/s (%s) ' \
                % (add_suffix(s.upload_rate), add_suffix(s.total_upload))
            out += '\n'
            

            if s.state != lt.torrent_status.seeding:
                out += 'info-hash: %s\n' % s.info_hashes
                out += 'next announce: %s\n' % s.next_announce
                out += 'tracker: %s\n' % s.current_tracker 

            with open(self._log_path + "/" + str(self._UUID) + ".status", 'w') as f:
                print(out, file=f)
            time.sleep(1)

        self._messaging_logger.info("Preparing download summary for Email")
        emailContent = "The server has finished the download of torrent: " + str(self._UUID) + "\n"
        emailContent += "Torrent name: %s \n" % (s.name)
        emailContent += "Summary: \n"
        emailContent += 'download: %s/s (%s) ' \
            % (add_suffix(s.download_rate), add_suffix(s.total_download))
        emailContent += 'upload: %s/s (%s) ' \
            % (add_suffix(s.upload_rate), add_suffix(s.total_upload))
        emailContent += '\n'
        
        msg = EmailMessage()
        msg["Subject"] = "Server Download Service"
        msg["From"] = self._sender_email
        msg["To"] = "mail@gmail.com"
        
        msg.set_content(emailContent)
        
        self.sendMail(msg) 


if __name__ == "__main__":
    fire.Fire({
        "downloader": Downloader
    })
