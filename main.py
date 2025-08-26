import os.path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ["https://www.googleapis.com/auth/contacts.readonly"]


def list_ten_contacts():
  creds = None
  if os.path.exists("token.json"):
    creds = Credentials.from_authorized_user_file("token.json", SCOPES)
  if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
      creds.refresh(Request())
    else:
      flow = InstalledAppFlow.from_client_secrets_file(
          "credentials.json", SCOPES
      )
      creds = flow.run_local_server(port=0)
    with open("token.json", "w") as token:
      token.write(creds.to_json())

  try:
    service = build("people", "v1", credentials=creds)

    print("List 10 connection names")
    results = (
        service.people()
        .connections()
        .list(
            resourceName="people/me",
            pageSize=10,
            personFields="names,emailAddresses",
        )
        .execute()
    )
    connections = results.get("connections", [])

    for person in connections:
      names = person.get("names", [])
      if names:
        name = names[0].get("displayName")
        print(name)
  except HttpError as err:
    print(err)


if __name__ == "__main__":
  main()