#!/usr/bin/env python
# coding: utf-8

# In[10]:


from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver import ActionChains
from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException, NoSuchWindowException, InvalidSessionIdException
import getpass
from cryptography.fernet import Fernet
import os, sys, csv, time
from pathlib import Path
import dotenv
from io import StringIO
from pandas import read_csv

# use CONTROL or COMMAND selected by OS
if sys.platform == 'darwin':
    CTRL = Keys.COMMAND
else: CTRL = Keys.CONTROL

desktop = os.path.expanduser("~/Desktop")
setup_path = desktop
verbose = '-v' in sys.argv
if '-p' in sys.argv:
    setup_path = sys.argv[sys.argv.index('-p')+1]


# In[2]:


def open_driver():
    if not os.path.exists(setup_path):
        raise TypeError('SETUP PATH IS NOT VALID OR INACCESSIBLE')
    
    root = os.path.join(setup_path, 'Dersler')
    download_dir = os.path.join(root, '.Downloads')
    
    if not os.path.exists(download_dir):
        os.makedirs(download_dir)
    if not os.path.exists(root):
        os.makedirs(root)

    os.chdir(root)
    
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument('log-level=3')
    prefs = {"download.default_directory" : download_dir}
    chrome_options.add_experimental_option('prefs', prefs)
    if not verbose:
        chrome_options.add_argument('--headless') # by choice
    
    # Driver
    chrome_driver_path = 'chromedriver'
    driver = webdriver.Chrome(chrome_driver_path, chrome_options=chrome_options)

    # Login Website
    driver.get('https://girisv3.itu.edu.tr')
    return driver, root, download_dir

def login(driver):
    # Login
    
    dotenv.load_dotenv(os.path.join(root, '.env'))
    
    username = os.environ.get('USR')
    enc_password = os.environ.get('PSW')
    
    # Find spaces to fill
    user_xpath = '//*[@id="ContentPlaceHolder1_tbUserName"]'
    password_xpath = '//*[@id="ContentPlaceHolder1_tbPassword"]'
    user_place = driver.find_element(By.XPATH, user_xpath)
    password_place = driver.find_element(By.XPATH, password_xpath)
    
    # Fill the spaces
    user_place.send_keys(username)
    fernet = Fernet(bytes(os.environ.get('KEY'), 'utf-8'))
    password = fernet.decrypt(bytes(enc_password, 'utf-8')).decode()
    password_place.send_keys(password)
    driver.find_element(By.XPATH, '//*[@id="ContentPlaceHolder1_btnLogin"]').click()
    del fernet, enc_password, username, password
    
    # Go to Ninova
    driver.get("https://ninova.itu.edu.tr/Kampus1")
    
    if 'girisv3' in driver.current_url:
        return False
    
    return True

def login_check(setup_path, driver):
    # save login informations
    loginfo_path = os.path.join(root, '.env')
    
    if not os.path.exists(loginfo_path) or (os.path.exists(loginfo_path) and os.path.getsize(loginfo_path) == 0):
        loginfo = open(loginfo_path, 'w')
        loginfo.close()
        username = input('Username:')
        password = getpass.getpass()

        # Hash password
        key = Fernet.generate_key()
        fernet = Fernet(key)
        enc_password = fernet.encrypt(password.encode())
        dotenv.set_key(loginfo_path, "KEY", str(key, encoding='utf-8'))
        dotenv.set_key(loginfo_path, "USR", username)
        dotenv.set_key(loginfo_path, "PSW", str(enc_password, encoding='utf-8'))
        del fernet, key, enc_password, username, password

    # Validate login information
    if not login(driver):
        os.remove(loginfo_path)
        raise TypeError('Username or password is incorrect.')
        
    return root, download_dir

def open_course_websites(driver):
    # Open all course websites in a new tab
    lessons = driver.find_element(By.XPATH, '//*[@id="aspnetForm"]/div[3]/div[3]/div[2]/div/div[1]/ul')
    lessons_links = lessons.find_elements(By.TAG_NAME, 'a')
    
    actions = ActionChains(driver)
    for i in lessons_links:
        actions.key_down(CTRL).click(i).key_up(CTRL)
        actions.perform()
    
    driver.switch_to.window(driver.window_handles[0])
    driver.close()
    
def open_class_course_files(driver):
    actions = ActionChains(driver)
    for i in driver.window_handles:
        driver.switch_to.window(i)
        for i in driver.find_elements(By.CLASS_NAME, 'panoElemani'):
            pano_element = i.find_element(By.CSS_SELECTOR, 'h2 > a')
            if pano_element.text in ['Ders Dosyaları', 'Sınıf Dosyaları', 'Class Files', 'Course Files']:
                actions.key_down(CTRL).click(pano_element).key_up(CTRL)
                actions.perform()
        driver.close()
        
def get_local_path(driver, root):
    path_list = driver.find_element(By.CLASS_NAME, 'ic').text.split('/')[2:]
    online_folder_xpath = '//*[@id="aspnetForm"]/div[3]/div[3]/div[3]/div/div[2]/div[1]'
    online_folder_path = driver.find_element(By.XPATH, online_folder_xpath).text
    if len(online_folder_path) != 1:
        online_path = os.path.join(*list(map(str.strip, path_list)), online_folder_path[1:-1])
    else:
        online_path = os.path.join(*list(map(str.strip, path_list)))
    
    path = os.path.join(root, online_path)

    if not os.path.exists(path):
        os.makedirs(path)
    return path, online_path

def download_and_move(driver, root, download_dir):
    counter = 0
    try:
        while len(driver.window_handles) > 0:
            archive = open('.archive.csv', 'a+', newline='')
            fieldnames = ['path', 'date']
            writer = csv.DictWriter(archive, fieldnames=fieldnames)
            archive.seek(0)
            if archive.read() == '':    
                writer.writeheader()
                archive.close()

                archive = open('.archive.csv', 'a+', newline='')
                writer = csv.DictWriter(archive, fieldnames=fieldnames) 

            archive_paths = list(map(str, read_csv('.archive.csv')['path']))
            tbody_xpath = '//*[@id="aspnetForm"]/div[3]/div[3]/div[3]/div/div[2]/table[2]/tbody'
            for page in driver.window_handles:
                driver.switch_to.window(page)
                files_table = driver.find_element(By.XPATH, tbody_xpath)
                actions = ActionChains(driver)

                try:
                    cells = files_table.find_elements(By.CSS_SELECTOR, 'tr')
                    for row in cells:
                        try:
                            course_local_path, online_path = get_local_path(driver, root)
                            link = row.find_element(By.CSS_SELECTOR, 'td > a')
                            size = row.find_element(By.CSS_SELECTOR, 'td:nth-child(2)').text
                            date = row.find_element(By.CSS_SELECTOR, 'td:nth-child(3)').text
                            online_abs_path = os.path.join(online_path.replace(',', ' '), link.text.replace(',', ' '))
                            isFolder = row.find_element(By.CSS_SELECTOR, 'td:nth-child(1) > img').get_attribute('src').endswith('folder.png')
                            if (not online_abs_path in archive_paths) and not size == '':
                                actions.key_down(CTRL).click(link).key_up(CTRL)
                                actions.perform()
                                if isFolder:
                                    continue
                            else:
                                continue

                            download_dir_content = os.listdir(download_dir)
                            if '.DS_Store' in download_dir_content: download_dir_content.remove('.DS_Store')

                            # Wait until file is downloaded
                            while not download_dir_content:
                                time.sleep(1)
                                download_dir_content = os.listdir(download_dir)
                                if '.DS_Store' in download_dir_content: download_dir_content.remove('.DS_Store')

                            if len(download_dir_content) == 1:
                                downloading_file = download_dir_content[0]
                                while downloading_file.endswith('.crdownload'):
                                    download_dir_content = os.listdir(download_dir)
                                    if '.DS_Store' in download_dir_content: download_dir_content.remove('.DS_Store')
                                    if len(download_dir_content) == 1:
                                        downloading_file = download_dir_content[0]
                                    else:
                                        raise IndexError('There are many or no files downloading.')

                                    time.sleep(0.3) # Time can be estimated in future work (file size / internet speed)

                                downloaded_path = os.path.join(download_dir, downloading_file)
                                os.system(f'mv "{downloaded_path}" "{course_local_path}"')
                                writer.writerow({'path':online_abs_path, 'date':date.replace(',', ' ')})
                            else:
                                raise IndexError('There are many or no files downloading.')
                            
                            counter += 1

                        except NoSuchElementException or NoSuchWindowException:
                            pass

                except StaleElementReferenceException or NoSuchElementException or NoSuchWindowException:
                    pass

                driver.close()
            archive.close()
    except InvalidSessionIdException:
        archive.close()
        if counter > 1: print(f'{counter} files are downloaded.')
        else: print(f'{counter} file is downloaded.')


# In[3]:


driver, root, download_dir = open_driver()
login_check(setup_path, driver)
open_course_websites(driver)
open_class_course_files(driver)
download_and_move(driver, root, download_dir)
driver.quit()

