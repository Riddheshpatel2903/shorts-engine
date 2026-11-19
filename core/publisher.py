"""
Social Media Auto-Publishing Module for YouTube Shorts and Instagram Reels.
Handles OAuth credentials, metadata formatting, and automatic video upload.
"""

import os
import json
import logging
import urllib.request
import urllib.parse
from pathlib import Path
from typing import Dict, Any, Optional

from config import WORKSPACE_DIR

logger = logging.getLogger("ViralShortsEngine.Publisher")

CREDENTIALS_FILE = Path(WORKSPACE_DIR) / "social_credentials.json"


class SocialPublisher:
    """Manages YouTube Data API v3 and Instagram Reels publishing."""

    def __init__(self):
        self.credentials_path = CREDENTIALS_FILE
        self._load_credentials()

    def _load_credentials(self):
        if self.credentials_path.exists():
            try:
                with open(self.credentials_path, "r", encoding="utf-8") as f:
                    self.creds = json.load(f)
            except Exception:
                self.creds = self._default_creds()
        else:
            self.creds = self._default_creds()
            self._save_credentials()

    def _default_creds(self) -> Dict[str, Any]:
        return {
            "youtube": {
                "enabled": False,
                "client_id": "",
                "client_secret": "",
                "refresh_token": "",
                "access_token": "",
                "channel_id": "",
                "privacy": "public"  # public, unlisted, private
            },
            "instagram": {
                "enabled": False,
                "app_id": "",
                "app_secret": "",
                "access_token": "",
                "account_id": "",
                "username": ""
            },
            "auto_publish_on_render": False
        }

    def _save_credentials(self):
        try:
            with open(self.credentials_path, "w", encoding="utf-8") as f:
                json.dump(self.creds, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not save social credentials: {e}")

    def get_status(self) -> Dict[str, Any]:
        """Returns connection status for YouTube and Instagram."""
        yt = self.creds.get("youtube", {})
        ig = self.creds.get("instagram", {})
        has_yt = bool(yt.get("access_token") or yt.get("refresh_token"))
        has_ig = bool(ig.get("access_token") and ig.get("account_id"))
        return {
            "youtube_connected": has_yt,
            "youtube_channel": yt.get("channel_id") or ("Auto-Configured" if has_yt else "Not connected"),
            "youtube_privacy": yt.get("privacy", "public"),
            "instagram_connected": has_ig,
            "instagram_user": ig.get("username") or ("Connected" if has_ig else "Not connected"),
            "instagram_account_id": ig.get("account_id", ""),
            "auto_publish": self.creds.get("auto_publish_on_render", False)
        }

    def generate_youtube_auth_url(self, client_id: str, redirect_uri: str = "http://localhost:8501/") -> str:
        """Generates the Google OAuth 2.0 authorization URL for YouTube Shorts upload."""
        scopes = [
            "https://www.googleapis.com/auth/youtube.upload",
            "https://www.googleapis.com/auth/youtube.readonly"
        ]
        params = {
            "client_id": client_id.strip(),
            "redirect_uri": redirect_uri.strip(),
            "response_type": "code",
            "scope": " ".join(scopes),
            "access_type": "offline",
            "prompt": "consent"
        }
        return f"https://accounts.google.com/o/oauth2/auth?{urllib.parse.urlencode(params)}"

    def exchange_youtube_code(self, client_id: str, client_secret: str, auth_code: str, redirect_uri: str = "http://localhost:8501/") -> Dict[str, Any]:
        """Exchanges Google authorization code for permanent refresh token and access token."""
        # Clean and sanitize auth_code aggressively
        clean_code = auth_code.strip()
        if "code=" in clean_code:
            match = re.search(r"code=([^&#\s]+)", clean_code)
            if match:
                clean_code = match.group(1)
        
        # Strip any accidental &scope= or # hash fragment or spaces
        if "&" in clean_code:
            clean_code = clean_code.split("&")[0].strip()
        if "#" in clean_code:
            clean_code = clean_code.split("#")[0].strip()
        
        # Ensure it is unquoted once so urlencode doesn't double-encode (%252F instead of %2F)
        clean_code = urllib.parse.unquote(clean_code).strip()

        # Clean redirect_uri (strip whitespace and ensure exact matching)
        clean_redirect = redirect_uri.strip()

        url = "https://oauth2.googleapis.com/token"
        data = urllib.parse.urlencode({
            "client_id": client_id.strip(),
            "client_secret": client_secret.strip(),
            "code": clean_code,
            "grant_type": "authorization_code",
            "redirect_uri": clean_redirect
        }).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                access_token = res.get("access_token")
                refresh_token = res.get("refresh_token")

                self.creds["youtube"]["client_id"] = client_id.strip()
                self.creds["youtube"]["client_secret"] = client_secret.strip()
                if access_token:
                    self.creds["youtube"]["access_token"] = access_token
                if refresh_token:
                    self.creds["youtube"]["refresh_token"] = refresh_token
                self.creds["youtube"]["enabled"] = True
                self._save_credentials()

                return {
                    "success": True,
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "expires_in": res.get("expires_in")
                }
        except urllib.error.HTTPError as he:
            err_body = he.read().decode("utf-8", errors="ignore")
            logger.error(f"HTTPError exchanging YouTube authorization code: {err_body}")
            try:
                err_json = json.loads(err_body)
                err_msg = err_json.get("error_description") or err_json.get("error") or str(he)
            except Exception:
                err_msg = err_body[:200]
            return {"success": False, "error": f"{he.code} - {err_msg}"}
        except Exception as e:
            logger.error(f"Failed to exchange YouTube authorization code: {e}")
            return {"success": False, "error": str(e)}

    def refresh_youtube_token_if_possible(self) -> Optional[str]:
        """Uses stored refresh_token to obtain a fresh access_token when expired."""
        yt = self.creds.get("youtube", {})
        client_id = yt.get("client_id")
        client_secret = yt.get("client_secret")
        refresh_token = yt.get("refresh_token")

        if not (client_id and client_secret and refresh_token):
            return yt.get("access_token")

        url = "https://oauth2.googleapis.com/token"
        data = urllib.parse.urlencode({
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token"
        }).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                new_token = res.get("access_token")
                if new_token:
                    self.creds["youtube"]["access_token"] = new_token
                    self._save_credentials()
                    return new_token
        except Exception as e:
            logger.warning(f"Could not auto-refresh YouTube access token: {e}")
        return yt.get("access_token")

    def generate_instagram_auth_url(self, app_id: str, redirect_uri: str = "https://localhost/") -> str:
        """Generates the Meta OAuth dialog URL for Instagram Graph API."""
        scopes = [
            "instagram_basic",
            "instagram_content_publish",
            "pages_show_list",
            "pages_read_engagement"
        ]
        params = {
            "client_id": app_id.strip(),
            "redirect_uri": redirect_uri.strip(),
            "scope": ",".join(scopes),
            "response_type": "token"
        }
        return f"https://www.facebook.com/v19.0/dialog/oauth?{urllib.parse.urlencode(params)}"

    def exchange_instagram_long_lived_token(self, app_id: str, app_secret: str, short_token: str) -> Dict[str, Any]:
        """Exchanges short-lived Meta user token for 60-day long-lived access token and auto-detects Account ID."""
        url = (
            f"https://graph.facebook.com/v19.0/oauth/access_token?"
            f"grant_type=fb_exchange_token&client_id={app_id.strip()}&client_secret={app_secret.strip()}&fb_exchange_token={short_token.strip()}"
        )
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=15) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                long_lived_token = res.get("access_token")

                if not long_lived_token:
                    return {"success": False, "error": "Did not receive long-lived access token from Meta."}

                # Auto-detect connected Instagram Business / Creator Account ID
                detect_res = self.detect_instagram_account_id(long_lived_token)
                acc_id = detect_res.get("account_id", "")
                page_name = detect_res.get("page_name", "")

                self.creds["instagram"]["app_id"] = app_id.strip()
                self.creds["instagram"]["app_secret"] = app_secret.strip()
                self.creds["instagram"]["access_token"] = long_lived_token
                if acc_id:
                    self.creds["instagram"]["account_id"] = acc_id
                if page_name:
                    self.creds["instagram"]["username"] = page_name
                self.creds["instagram"]["enabled"] = True
                self._save_credentials()

                return {
                    "success": True,
                    "access_token": long_lived_token,
                    "account_id": acc_id,
                    "page_name": page_name,
                    "expires_in": res.get("expires_in")
                }
        except Exception as e:
            logger.error(f"Failed to exchange Meta/Instagram token: {e}")
            return {"success": False, "error": str(e)}

    def detect_instagram_account_id(self, access_token: str) -> Dict[str, Any]:
        """Queries Facebook Pages to auto-discover the linked Instagram Professional Account ID."""
        url = f"https://graph.facebook.com/v19.0/me/accounts?fields=name,instagram_business_account&access_token={access_token.strip()}"
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                for page in data.get("data", []):
                    ig_acc = page.get("instagram_business_account")
                    if ig_acc and "id" in ig_acc:
                        return {"success": True, "account_id": ig_acc["id"], "page_name": page.get("name", "")}
                return {"success": False, "error": "No Instagram Professional account found attached to Facebook pages."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def update_credentials(
        self,
        yt_token: Optional[str] = None,
        yt_channel: Optional[str] = None,
        yt_privacy: Optional[str] = None,
        yt_client_id: Optional[str] = None,
        yt_client_secret: Optional[str] = None,
        ig_token: Optional[str] = None,
        ig_account_id: Optional[str] = None,
        ig_username: Optional[str] = None,
        ig_app_id: Optional[str] = None,
        ig_app_secret: Optional[str] = None,
        auto_publish: Optional[bool] = None
    ):
        """Updates and persists social credentials."""
        if yt_token is not None:
            self.creds["youtube"]["access_token"] = yt_token.strip()
        if yt_channel is not None:
            self.creds["youtube"]["channel_id"] = yt_channel.strip()
        if yt_privacy is not None:
            self.creds["youtube"]["privacy"] = yt_privacy
        if yt_client_id is not None:
            self.creds["youtube"]["client_id"] = yt_client_id.strip()
        if yt_client_secret is not None:
            self.creds["youtube"]["client_secret"] = yt_client_secret.strip()

        if ig_token is not None:
            self.creds["instagram"]["access_token"] = ig_token.strip()
        if ig_account_id is not None:
            self.creds["instagram"]["account_id"] = ig_account_id.strip()
        if ig_username is not None:
            self.creds["instagram"]["username"] = ig_username.strip()
        if ig_app_id is not None:
            self.creds["instagram"]["app_id"] = ig_app_id.strip()
        if ig_app_secret is not None:
            self.creds["instagram"]["app_secret"] = ig_app_secret.strip()

        if auto_publish is not None:
            self.creds["auto_publish_on_render"] = auto_publish

        self._save_credentials()

    def publish_to_youtube(self, video_path: str, title: str, description: str, tags: Optional[str] = None) -> Dict[str, Any]:
        """
        Uploads video to YouTube Shorts via YouTube Data API v3 with auto-refreshing OAuth.
        """
        yt = self.creds.get("youtube", {})
        access_token = self.refresh_youtube_token_if_possible() or yt.get("access_token")
        
        if not access_token:
            return {
                "success": False,
                "platform": "YouTube",
                "error": "YouTube account not connected. Please enter your OAuth Access Token in Settings."
            }

        if not Path(video_path).exists():
            return {"success": False, "platform": "YouTube", "error": f"Video file not found: {video_path}"}

        # Ensure #Shorts is in title/description for Shorts shelf indexing
        final_title = title if "#Shorts" in title else f"{title} #Shorts"[:100]
        final_desc = f"{description}\n\n#Shorts #Viral"
        privacy = yt.get("privacy", "public")

        try:
            # Metadata initialization request
            upload_url = "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status"
            metadata = {
                "snippet": {
                    "title": final_title,
                    "description": final_desc,
                    "tags": [t.strip("#") for t in (tags or "").split() if t][:10],
                    "categoryId": "20"  # Gaming/Entertainment
                },
                "status": {
                    "privacyStatus": privacy,
                    "selfDeclaredMadeForKids": False
                }
            }

            req = urllib.request.Request(
                upload_url,
                data=json.dumps(metadata).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json; charset=UTF-8",
                    "X-Upload-Content-Type": "video/mp4"
                },
                method="POST"
            )

            with urllib.request.urlopen(req, timeout=15) as resp:
                upload_endpoint = resp.headers.get("Location")

            if not upload_endpoint:
                return {"success": False, "platform": "YouTube", "error": "Did not receive upload endpoint from YouTube."}

            # Stream video content
            with open(video_path, "rb") as vid_file:
                vid_data = vid_file.read()

            upload_req = urllib.request.Request(
                upload_endpoint,
                data=vid_data,
                headers={"Content-Type": "video/mp4"},
                method="PUT"
            )

            with urllib.request.urlopen(upload_req, timeout=60) as final_resp:
                res_data = json.loads(final_resp.read().decode("utf-8"))
                video_id = res_data.get("id")

            return {
                "success": True,
                "platform": "YouTube",
                "video_id": video_id,
                "url": f"https://youtube.com/shorts/{video_id}"
            }

        except Exception as e:
            logger.error(f"YouTube publishing failed: {e}")
            return {
                "success": False,
                "platform": "YouTube",
                "error": str(e)
            }

    def publish_to_instagram(self, video_url_or_path: str, caption: str) -> Dict[str, Any]:
        """
        Publishes video as an Instagram Reel using Instagram Graph API.
        Supports both remote URLs and local video MP4 file uploads via Meta Resumable Upload.
        """
        ig = self.creds.get("instagram", {})
        access_token = ig.get("access_token")
        account_id = ig.get("account_id")

        if not access_token or not account_id:
            return {
                "success": False,
                "platform": "Instagram",
                "error": "Instagram account not connected. Please enter Access Token & Account ID in Settings."
            }

        try:
            local_path = Path(video_url_or_path)
            is_local = local_path.exists() and local_path.is_file()

            if is_local:
                # 1. Initialize resumable container for local file
                endpoint = f"https://graph.facebook.com/v19.0/{account_id}/media"
                params = {
                    "media_type": "REELS",
                    "upload_type": "resumable",
                    "caption": caption,
                    "access_token": access_token
                }
                data = urllib.parse.urlencode(params).encode("utf-8")
                req = urllib.request.Request(endpoint, data=data, method="POST")

                with urllib.request.urlopen(req, timeout=15) as resp:
                    res = json.loads(resp.read().decode("utf-8"))
                    container_id = res.get("id")
                    upload_uri = res.get("uri")

                if not container_id or not upload_uri:
                    return {"success": False, "platform": "Instagram", "error": "Failed to initialize Instagram Reels container."}

                # 2. Upload binary video bytes to Meta rupload endpoint
                with open(local_path, "rb") as vf:
                    vid_bytes = vf.read()

                upload_headers = {
                    "Authorization": f"OAuth {access_token}",
                    "offset": "0",
                    "file_size": str(len(vid_bytes)),
                    "Content-Type": "application/octet-stream"
                }
                up_req = urllib.request.Request(upload_uri, data=vid_bytes, headers=upload_headers, method="POST")
                with urllib.request.urlopen(up_req, timeout=60) as up_resp:
                    pass

            else:
                # Web URL container creation
                endpoint = f"https://graph.facebook.com/v19.0/{account_id}/media"
                params = {
                    "media_type": "REELS",
                    "video_url": video_url_or_path,
                    "caption": caption,
                    "access_token": access_token
                }
                data = urllib.parse.urlencode(params).encode("utf-8")
                req = urllib.request.Request(endpoint, data=data, method="POST")

                with urllib.request.urlopen(req, timeout=15) as resp:
                    res = json.loads(resp.read().decode("utf-8"))
                    container_id = res.get("id")

                if not container_id:
                    return {"success": False, "platform": "Instagram", "error": "Failed to create media container."}

            # 3. Publish container
            pub_endpoint = f"https://graph.facebook.com/v19.0/{account_id}/media_publish"
            pub_params = {"creation_id": container_id, "access_token": access_token}
            pub_data = urllib.parse.urlencode(pub_params).encode("utf-8")
            pub_req = urllib.request.Request(pub_endpoint, data=pub_data, method="POST")

            with urllib.request.urlopen(pub_req, timeout=20) as pub_resp:
                pub_res = json.loads(pub_resp.read().decode("utf-8"))
                media_id = pub_res.get("id")

            return {
                "success": True,
                "platform": "Instagram",
                "media_id": media_id,
                "url": f"https://instagram.com/reel/{media_id}"
            }

        except Exception as e:
            logger.error(f"Instagram publishing failed: {e}")
            return {
                "success": False,
                "platform": "Instagram",
                "error": str(e)
            }

    def auto_publish_if_enabled(self, video_path: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Automatically posts to connected accounts if auto-publish is toggled on."""
        if not self.creds.get("auto_publish_on_render", False):
            return {"triggered": False, "message": "Auto-publish is disabled"}

        results = {}
        title = metadata.get("title", "Viral Short")
        caption = f"{metadata.get('instagram_caption', '')}\n\n{metadata.get('hashtags', '')}"
        tags = metadata.get("hashtags", "")

        if self.creds.get("youtube", {}).get("access_token"):
            results["youtube"] = self.publish_to_youtube(video_path, title, caption, tags)

        if self.creds.get("instagram", {}).get("access_token"):
            results["instagram"] = self.publish_to_instagram(video_path, caption)

        return {"triggered": True, "results": results}


# Singleton instance
publisher = SocialPublisher()
