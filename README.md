# Move Issues from Jira to Gitlab
Python 3 Script for moving issues from JIRA to Gitlab.

## How to use

Make sure that the gitlab user is assigned to your gitlab project and exists in the user mapping inside the Script. 

The user has to be an ***Owner***. This is required for setting specific gitlab_issue_ids to match with the jira ticket numbers.

Before you start the Script make sure you have set all the variables inside the script:


```python
JIRA_URL = 'https://your-jira-url.com/'
JIRA_ACCOUNT = ('jira-username', 'jira-password')
JIRA_BOARD_ID = 1
# afaik this is the json field for sprints
JIRA_CUSTOM_SPRINT_FIELD = 'customfield_10005'
# the JIRA project ID (short)
JIRA_PROJECT = 'PRO'
GITLAB_URL = 'http://your-gitlab-url.tld/'
# this token will be used whenever the API is invoked and
# the script will be unable to match the jira's author of the comment / attachment / issue
# this identity will be used instead.
GITLAB_TOKEN = 'get-this-token-from-your-profile'
# the project in gitlab that you are importing issues to.
GITLAB_PROJECT = 'namespaced/project/name'
# the numeric project ID. If you don't know it, the script will search for it
# based on the project name.
GITLAB_PROJECT_ID = None
# set this to false if JIRA / Gitlab is using self-signed certificate.
VERIFY_SSL_CERTIFICATE = True


GITLAB_USER_NAMES = {
    'jira': 'gitlab',
}

...

```

<br>

## User Mapping

It can happen, that the Jira username and the gitlab username are not the same. To fix this you can define an username_mapping on the top of the script.

To List an Example of all releant jira users inside the project you are trying to move wait until the Jira Issues have loaded and then Type ***2***.
