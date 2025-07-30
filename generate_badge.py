from db.database import DatabaseManager
import os

SVG_FOLDER = 'img/compiler'

class RepoReport:
    def __init__(self, git_username, repository_name):
        self.hspace = 5
        self.taglist = []
        self.code = ''
        self.height = 20
        self.width=0

        self.git_username = git_username
        self.repository_name = repository_name

        self.db_update()

    def db_update(self):
        self.taglist = []

        db_manager = DatabaseManager()
        reg = db_manager.get_repository_status(self.git_username, self.repository_name)
        
        for release in reg:
            version = release['version_name']
            test_status = release['test_status']
            delivery_status = release['delivery_status']
            self.addtag(version, delivery_status, test_status)

    def save(self):
        self.compile()
        
        svg_file = '{}_{}.svg'.format(self.git_username, self.repository_name)
        svg_file = os.path.join(SVG_FOLDER, svg_file)

        with open(svg_file, 'w') as arq:
            arq.write(self.code)
            arq.close()

    def compile(self):
        tagcode = ''
        xpos = 0

        for tag in self.taglist:
            tagcode += tag.compile(xpos)
            xpos = xpos + tag.width + self.hspace

        self.width = xpos - self.hspace

        self.code = '<svg xmlns="http://www.w3.org/2000/svg" width="{}" height="{}">\n'.format(self.width, self.height) + \
                    '<linearGradient id="a" x2="0" y2="100%">\n' + \
                    '    <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>\n' + \
                    '    <stop offset="1" stop-opacity=".1"/>\n' + \
                    '</linearGradient>\n\n'

        self.code += tagcode

        self.code += '</svg>'

        return(self.code)

    def addtag(self, version, deliverystatus, teststatus):
        tagreport = TagReport(version, teststatus, deliverystatus, self.height)
        self.taglist.append(tagreport)
        
class TagReport():
    def __init__(self, version, teststatus, deliverystatus, height):
        
        self.versionwidth = 40
        self.versiontextoffset = 18
        
        self.deliverywidth = 50
        self.deliverywidthoffset = 5
        self.deliverytextoffset = 25

        self.testwidth = 40
        self.testtextoffset = 18

        self.width = self.versionwidth + self.deliverywidth + self.testwidth - self.deliverywidthoffset
        self.height = height
     

        self.code = ''
        self.version = version
        self.setteststatus(teststatus)
        self.setdeliverystatus(deliverystatus)

    def setteststatus(self, teststatus):
        if teststatus == 'ERROR':
            self.testcolor = '#ff4d4d'
            self.teststatus = 'Error'
        elif teststatus == 'PASS':
            self.testcolor = '#00b300'
            self.teststatus = 'Pass'
        elif teststatus == 'FAILED':
            self.testcolor = '#ff9933'
            self.teststatus = 'Fail'
        elif teststatus == 'NOT_FOUND':
            self.testcolor = '#c266ff'
            self.teststatus = 'To do'
        else:
            raise ValueError('Invalid test status: {}'.format(teststatus))

    def setdeliverystatus(self, deliverystatus):
        if deliverystatus == 'DELAYED':
            self.deliverycolor = '#cc00cc'
            self.deliverystatus = 'Delayed'
        elif deliverystatus == 'ON_TIME':
            self.deliverycolor = '#005ce6'
            self.deliverystatus = 'On time'
        else:
            raise ValueError('Invalid delivery status: {}'.format(deliverystatus))

    def compile(self, x):
        xdelivery = x + self.versionwidth
        xtest = x + self.versionwidth + self.deliverywidth - self.deliverywidthoffset

        xtextversion = x + self.versiontextoffset
        xtextdelivery = x + self.versionwidth + self.deliverytextoffset
        xtexttest = x + self.versionwidth + self.deliverywidth + self.testtextoffset

        self.code = '<rect rx="3" x="{}" y="0" width="{}" height="{}" fill="#595959"/>\n'.format(x, self.width, self.height) + \
                    '<rect rx="3" x="{}" y="0" width="{}" height="{}" fill="{}"/>\n'.format(xtest, self.testwidth, self.height, self.testcolor) + \
                    '<rect rx="0" x="{}" y="0" width="{}" height="{}" fill="{}"/>\n'.format(xdelivery, self.deliverywidth, self.height, self.deliverycolor) + \
                    '<g fill="#fff" text-anchor="middle" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11">\n' + \
                    '    <text x="{}" y="15" fill="#010101" fill-opacity=".3">{}</text><text x="{}" y="14">{}</text>\n'.format(xtextversion, self.version, xtextversion, self.version) + \
                    '    <text x="{}" y="15" fill="#010101" fill-opacity=".3">{}</text><text x="{}" y="14">{}</text>\n'.format(xtextdelivery, self.deliverystatus, xtextdelivery, self.deliverystatus) + \
                    '    <text x="{}" y="15" fill="#010101" fill-opacity=".3">{}</text><text x="{}" y="14">{}</text>\n'.format(xtexttest, self.teststatus, xtexttest, self.teststatus) + \
                    '</g>\n'
        return(self.code)
