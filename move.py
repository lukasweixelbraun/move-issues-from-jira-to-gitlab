# coding=utf-8

import requests
from requests.auth import HTTPBasicAuth
import re
from io import BytesIO
import urllib

JIRA_URL = 'https://your-jira-url.com/'
JIRA_ACCOUNT = ('jira-username', 'jira-password')
JIRA_BOARD_ID = 1
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

# IMPORTANT !!!
# make sure that user (in gitlab) has access to the project you are trying to
# import into. Otherwise the API request will fail.

# The GitLab user also has to have administrator or project owner rights
# This is required for setting specific gitlab issue ids to match with the jira ticket numbers

# jira user name as key, gitlab as value
# if you want dates and times to be correct, make sure every user is (temporarily) admin
GITLAB_USER_NAMES = {
    'jira': 'gitlab',
}

# fetch MAX_JIRA_TICKET_NUMBER
def fetch_latest_jira_ticket_number():
    issues_key = requests.get(
        JIRA_URL + '/rest/agile/1.0/board/%s/issue?jql=order+by+created+desc&maxResults=1' % JIRA_BOARD_ID,
        auth=HTTPBasicAuth(*JIRA_ACCOUNT),
        verify=VERIFY_SSL_CERTIFICATE,
        headers={'Content-Type': 'application/json'}
    ).json()['issues'][0]

    max_ticket_number = issues_key['key'].replace(JIRA_PROJECT + "-", "")
    return int(max_ticket_number)

def fetch_project_data():
    global GITLAB_PROJECT_ID

    if not GITLAB_PROJECT_ID:
        # find out the ID of the project.
        for project in requests.get(
            GITLAB_URL + 'api/v4/projects',
            headers={'PRIVATE-TOKEN': GITLAB_TOKEN},
        ).json():
            if project['path_with_namespace'] == GITLAB_PROJECT:
                GITLAB_PROJECT_ID = project['id']
                break

        if not GITLAB_PROJECT_ID:
            raise Exception("Unable to find %s in gitlab!" % GITLAB_PROJECT)

# fetch jira sprints
def fetch_sprints():
    sprints = requests.get(
        JIRA_URL + '/rest/agile/1.0/board/%s/sprint' % JIRA_BOARD_ID,
        auth=HTTPBasicAuth(*JIRA_ACCOUNT),
        verify=VERIFY_SSL_CERTIFICATE,
        headers={'Content-Type': 'application/json'}
    ).json()['values']

    return sprints

# fetch gitlab users to add assignee
def fetch_users():
    users = requests.get(
        GITLAB_URL + 'api/v4/users?per_page=100&page=1',
        headers={'PRIVATE-TOKEN': GITLAB_TOKEN},
        verify=VERIFY_SSL_CERTIFICATE,
    ).json()

    return users

# fetch jira milestones
def fetch_milestones():
    milestones = requests.get(
        GITLAB_URL + 'api/v4/projects/%s/milestones' % GITLAB_PROJECT_ID,
        headers={'PRIVATE-TOKEN': GITLAB_TOKEN},
        verify=VERIFY_SSL_CERTIFICATE,
    ).json()

    return milestones

def fetch_issue_data(jira_key):
    # fetch jira issue data with jiraKey
    issue_response = requests.get(
        JIRA_URL + '/rest/api/2/issue/%s' % jira_key,
        auth=HTTPBasicAuth(*JIRA_ACCOUNT),
        verify=VERIFY_SSL_CERTIFICATE,
        headers={'Content-Type': 'application/json'}
    )

    return issue_response

def get_assignee_id(assignee):
    # get assignee
    assignee_name = ''
    if assignee:
        assignee_name = assignee.get('name', 0)

    assignee_id = None
    if assignee_name != '':
        for user in users:
            if user['username'] == GITLAB_USER_NAMES.get(assignee_name, assignee_name):
                assignee_id = user['id']
                break

def sync_sprints(issue):
    # get sprints
    assigned_sprints = []
    if issue['fields'].get(JIRA_CUSTOM_SPRINT_FIELD):
        for customfield in issue['fields'].get(JIRA_CUSTOM_SPRINT_FIELD):
            sprint_id = customfield[customfield.index("id=")+3:customfield.index(",")]
            for sprint in sprints:
                if str(sprint['id']) == sprint_id:
                    assigned_sprints.append(sprint)


    last_milestone_id = None
    exists = False
    milestone = ''
    closed = False
    startDate = None
    endDate = None

    if len(assigned_sprints) > 0:
        for sprint in assigned_sprints:
            exists = False
            last_milestone_id = None
            milestone = sprint.get('name')
            closed = sprint.get('state') == 'closed'
            startDate = sprint.get('startDate')
            endDate = sprint.get('endDate')

            startDateee = datetime.strptime(startDate[:10], "%Y-%m-%d")
            endDateee = datetime.strptime(endDate[:10], "%Y-%m-%d")

            if startDateee.date() >= endDateee.date():
                endDate = startDateee + timedelta(days=1)

            for milestne in MILESTONES:
                if milestone == milestne['title']:
                    exists = True
                    last_milestone_id = milestne['id']
                    break

            # create if it does not exist
            if milestone != '' and exists == False:
                new_milestone_resp = requests.post(
                    GITLAB_URL + 'api/v4/projects/%s/milestones' % GITLAB_PROJECT_ID,
                    headers={'PRIVATE-TOKEN': GITLAB_TOKEN},
                    verify=VERIFY_SSL_CERTIFICATE,
                    data={
                    'title': milestone,
                    'description': 'Jira %s' % milestone,
                    'start_date': startDate,
                    'due_date': endDate
                    }
                )

                # returns 201 if issue was created
                if new_milestone_resp.status_code != 201:
                    # if http status = 409 there already exists an gitlab milestone with this title
                    # skipping - only print response if there is an other http status
                    if new_milestone_resp.status_code != 400:
                        raise Exception(new_milestone_resp.json()['message'])
                    continue

                new_milestone = new_milestone_resp.json()
                last_milestone_id = new_milestone['id']
                MILESTONES.append(new_milestone)

                if closed:
                    res = requests.put(
                        GITLAB_URL + 'api/v4/projects/%s/milestones/%s?state_event=close' % (GITLAB_PROJECT_ID , new_milestone['id']),
                        headers={'PRIVATE-TOKEN': GITLAB_TOKEN},
                        verify=VERIFY_SSL_CERTIFICATE
                    ).json()

    return last_milestone_id

def sync_comments_and_attachments(issue_id, gl_issue):
    # get comments and attachments
    issue_info = requests.get(
        JIRA_URL + 'rest/api/2/issue/%s/?fields=attachment,comment' % issue_id,
        auth=HTTPBasicAuth(*JIRA_ACCOUNT),
        verify=VERIFY_SSL_CERTIFICATE,
        headers={'Content-Type': 'application/json'}
    ).json()

    for comment in issue_info['fields']['comment']['comments']:
        author = comment['author']['name']

        # edit body
        body = comment['body']
        if body == None: body = ""
        body = replace_hashtag(body)
        body = replace_issue_link(body)

        # add comment/note
        note_add = requests.post(
            GITLAB_URL + 'api/v4/projects/%s/issues/%s/notes' % (GITLAB_PROJECT_ID, gl_issue),
            headers={'PRIVATE-TOKEN': GITLAB_TOKEN,'SUDO': GITLAB_USER_NAMES.get(author, author)},
            verify=VERIFY_SSL_CERTIFICATE,
            data={
                'body': body,
                'created_at': comment['created']
            }
        )

    if len(issue_info['fields']['attachment']):
        for attachment in issue_info['fields']['attachment']:
            author = attachment['author']['name']

            # get jira attachment
            _file = requests.get(
                attachment['content'],
                auth=HTTPBasicAuth(*JIRA_ACCOUNT),
                verify=VERIFY_SSL_CERTIFICATE,
            )

            _content = BytesIO(_file.content)

            # upload attachment to gitlab
            file_info = requests.post(
                GITLAB_URL + 'api/v4/projects/%s/uploads' % GITLAB_PROJECT_ID,
                headers={'PRIVATE-TOKEN': GITLAB_TOKEN,'SUDO': GITLAB_USER_NAMES.get(author, author)},
                files={
                    'file': (
                        attachment['filename'],
                        _content
                    )
                },
                verify=VERIFY_SSL_CERTIFICATE
            )
            
            if file_info.status_code != 201:
                print(file_info.json()['message'])
                continue

            del _content

            # now we got the upload URL. Let's post the comment with an
            # attachment
            requests.post(
                GITLAB_URL + 'api/v4/projects/%s/issues/%s/notes' % (GITLAB_PROJECT_ID, gl_issue),
                headers={'PRIVATE-TOKEN': GITLAB_TOKEN,'SUDO': GITLAB_USER_NAMES.get(author, author)},
                verify=VERIFY_SSL_CERTIFICATE,
                data={
                    'body': file_info.json()['markdown'],
                    'created_at': attachment['created']
                }
            )

def close_issue(gl_issue, updated_at):
    # update updated_at
    res = requests.put(
        GITLAB_URL + 'api/v4/projects/%s/issues/%s' % (GITLAB_PROJECT_ID , gl_issue),
        headers={'PRIVATE-TOKEN': GITLAB_TOKEN},
        verify=VERIFY_SSL_CERTIFICATE,
        data={
            'updated_at': updated_at,
            'state_event': 'close'
        }
    ).json()

def set_updated_at(gl_issue, updated_at, created_at):
    # update updated_at
    res = requests.put(
        GITLAB_URL + 'api/v4/projects/%s/issues/%s' % (GITLAB_PROJECT_ID , gl_issue),
        headers={'PRIVATE-TOKEN': GITLAB_TOKEN},
        verify=VERIFY_SSL_CERTIFICATE,
        data={
            'updated_at': (created_at if updated_at == None else updated_at),
            'created_at': created_at
        }
    ).json()

def replace_hashtag(text):
    return text.replace("#", "\# ")

def replace_issue_link(text):
    return text.replace(JIRA_PROJECT + "-", "#")

def create_issue(ticket_number, issue):
    reporter = issue['fields']['reporter']['name']

    # get assignee
    assignee_id = get_assignee_id(issue['fields'].get('assignee'))

    # sync all sprints to milestones
    last_milestone_id = sync_sprints(issue)

    # create all labels
    labels = (issue['fields']['status']['statusCategory']['name'] + "," + 
                issue['fields']['issuetype']['name'] + "," + 
                issue['fields']['priority']['name'])
    
    for label in issue['fields']['labels']:
        labels += "," + label

    # edit description
    description = issue['fields']['description']
    if description == None: description = ""
    description = replace_hashtag(description)
    description = replace_issue_link(description)

    # create gitlab issue
    response = requests.post(
        GITLAB_URL + 'api/v4/projects/%s/issues' % GITLAB_PROJECT_ID,
        headers={'PRIVATE-TOKEN': GITLAB_TOKEN,'SUDO': GITLAB_USER_NAMES.get(reporter, reporter)},
        verify=VERIFY_SSL_CERTIFICATE,
        data={
            'iid': ticket_number,
            'title': issue['fields']['summary'],
            'description': description,
            'created_at': issue['fields']['created'],
            'assignee_id': assignee_id,
            'milestone_id': last_milestone_id,
            'labels': labels
        }
    )

    # returns 201 if issue was created
    if response.status_code != 201:
        # if http status = 409 there already exists an gitlab issue with this iid
        # skipping - only print response if there is an other http status
        if response.status_code != 409:
            raise Exception(response.json()['message'])
        return 0

    gl_issue = response.json()['iid']

    if issue['fields']['status']['statusCategory']['key'] == "done":
        close_issue(gl_issue, issue['fields']['updated'])

    return gl_issue

# STEP 1: create ALL issues
# STEP 2: create ALL comments
# STEP 3: update 'updated_at' for ALL issues
# this order is necessary to garantee, that all issue links (for example #145) are working
# and that 'last updated' is set correctly
def sync_issues():
    issues = []

    for ticket_number in range(1, MAX_JIRA_TICKET_NUMBER + 1):
        jira_key = JIRA_PROJECT + "-" + str(ticket_number)
        
        # fetch jira issue data with jiraKey
        issue_response = fetch_issue_data(jira_key)

        if issue_response.status_code == 404:
            print('Issue FUN-%s not found! Skipping issue id.' % ticket_number)
            continue

        issue = issue_response.json()

        # create issue
        gl_issue = create_issue(ticket_number, issue)
        if gl_issue <= 0:
            continue

        # add issue
        issue['new_iid'] = gl_issue
        issues.append(issue)
        print ("created issue #%s" % gl_issue)

    # sync all issues
    for issue in issues:
        gl_issue = issue['new_iid']
        sync_comments_and_attachments(issue['id'], gl_issue)
        set_updated_at(gl_issue, issue['fields']['updated'], issue['fields']['created'])
        print ("comments for issue #%s" % gl_issue)

    # update all updated_at for issues
    for issue in issues:
        gl_issue = issue['new_iid']
        set_updated_at(gl_issue, issue['fields']['updated'], issue['fields']['created'])
        print ("updated 'updated_at' for issue #%s" % gl_issue)

fetch_project_data()
users = fetch_users()
sprints = fetch_sprints()
MILESTONES = fetch_milestones()
MAX_JIRA_TICKET_NUMBER = fetch_latest_jira_ticket_number()

sync_issues()
