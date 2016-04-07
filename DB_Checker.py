import os
import time
import datetime
import subprocess
import threading
import Queue as queue
import logging
import six
import packaging
import packaging.version
import packaging.specifiers
from Tkinter import *
import ttk
import tkMessageBox
from functools import partial
import ibm_db
from excel_funcs import get_regions, get_config, fetch_table_names, get_input_params, get_validations, get_creds, get_sub_regions, get_usercolumnsel, retrieve_inputs_from_file, get_user_input_types, create_result_file, write_result

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


if os.path.exists("logs") != True:
	os.makedirs("logs")
handler = logging.FileHandler("logs\mylogs.log")
# handler = logging.StreamHandler()
handler.setLevel(logging.DEBUG)

formatter = logging.Formatter("%(asctime)s : %(levelname)s : %(message)s",
	"%Y-%m-%d %H:%M:%S")
handler.setFormatter(formatter)

logger.addHandler(handler)


class Application(Frame):
	def __init__(self, master=None):
		Frame.__init__(self, master)
		

		try:

			launch_stmt = """ **************************************************************************************** 
							Database Check Tool
							Version : 1.0
		              ****************************************************************************************
							"""
			logger.info(launch_stmt)
			logger.info("Initializing...")
			logger.info("Creating widgets...")

			# Creating all widgwts
			self.createWidget(master)

			logger.info("All widgets created successfully!!")

			# Retrieving all the regions from the DB Config workbook
			self.all_regions = get_regions()
			self.combo_region['values'] = self.all_regions
			logger.info("Regions retrieved : %s" % str(self.combo_region['values']), )

			# Retrieving user input types from the DB Config workbook
			self.userinput_combo['values'] = get_user_input_types()
			logger.info("Values assigned to userinput_combo : %s" % str(self.userinput_combo['values']), )
			self.userinput_combo.current(0)
			self.queue = queue.Queue()
			logger.info("Launching application...")

			# master.attributes("-fullscreen", True)


		except Exception, e:

			logger.error("Widgets creation failed. Error : %s" % (str(e), ))

		
		
		

	# Function for region change
	def region_change(self, event):
		""" Updates the Database Entry box, when the Region Combo Box is changed. """

		# Getting the selected region
		self.selected_region = self.combo_region.get()

		
		try:
			# Retreiving config values
			self.config = get_config(self.selected_region)

			logger.info("Config values retrieved : %s" % (str(self.config), ))

			# Assigning the values to the variables
			self.server = self.config[1]
			self.port = self.config[2]
			self.db = self.config[3]
			self.username.set(self.config[4])
			self.password.set(self.config[5])
			self.flag = self.config[6]

		except Exception, e:

			logger.error("Region Change - Error : %s" % (str(e), ))
			return 1

		# Setting up the db value
		self.db_val.set(self.db)

		return 0



	def db_connect(self):
		""" Connects to the IBM DB2 """

		self.connection_dict = {}

		# Preparing connection string.
		conn_str = "Database=%s;HOSTNAME=%s;PORT=%s;PROTOCOL=%s;UID=%s;PWD=%s;" % (str(self.db).strip(), str(self.server).strip(),
			str(self.port).strip(), "TCPIP", str(self.username.get()).strip(), str(self.password.get()).strip(),)

		logger.info("Connection string prepared : %s" % (str(conn_str), ))
		logger.info("Connecting...")

		try:

			self.conn = ibm_db.connect(conn_str,"","")
			self.statusbar_status['text'] = "Connected!!"

			logger.info("Yay Connected!!")

		except Exception, e:

			err = ibm_db.conn_errormsg()
			self.statusbar_status['text'] = "Connection Failed!!. Error Message : " + err

			logger.error("Connection failed!! :(")
			logger.error("DB Connection - Error : %s" % (str(e), ))
			return  1

		try:
			# Fetching the Table names from the Excel Sheet
			logger.info("Fetching table names...")
			tables1 = self.get_tables(self.combo_tables)
			logger.info("Run a Query Tables fetched : %s" % (str(tables1), ))

			tables2 = self.get_tables(self.waq_combo_tables)
			logger.info("Write a Query Tables fetched : %s" % (str(tables2), ))

		except Exception, e:
			
			logger.error("Error fetching the tables : %s" % (str(e), ))
			self.statusbar_status['text'] = "Error fetching tables from excel. Check logs."


		try:
			# Updating listbox
			logger.info("Updating Listbox...")
			sub_regs = self.update_listbox(self.flag)
			logger.info("Sub regions listbox updated : %s" % (str(sub_regs), ))

		except Exception, e:

			logger.error("Error loading the listbox - Error : %s" % (str(e), ))


		# Adding the connection object for the Main region in the connection dictionary

		self.connection_dict[self.selected_region] = self.conn

		# On successful connection
		self.connect_button['state'] = 'disabled'
		self.disconnect_button['state'] = 'normal'
		self.reg_button_connect['state'] = 'normal'
		self.get_schema_btn['state'] = 'normal'
		
		self.combo_region['state'] = 'disabled'
		self.combo_tables['state'] = "readonly"
		self.reg_query_button['state'] = 'normal'
		self.open_input_folder['state'] = 'normal'

		return 0



	def db_disconnect(self):
		""" Disconnects from the DB """

		if str(self.reg_button_disconnect['state']) == 'normal':
			tkMessageBox.showinfo("Warning", "Please disconnect the sub regions from the Rergession Tab.")
			return

		logger.info("Disconnecting from DB...")

		if self.conn:
			try:
				ibm_db.close(self.conn)
				self.statusbar_status['text'] = "Connection Closed!!"

				logger.info("Connection Closed.")
			except Exception, e:

				err = ibm_db.conn_errormsg()
				self.statusbar_status['text'] = "Connection is closed already!! :)"
				logger.error("Database disconnection failed : %s" % (str(e), ))
				return 1

		# On successful connection
		self.connect_button['state'] = 'normal'
		self.disconnect_button['state'] = 'disabled'
		self.reg_button_connect['state'] = 'disabled'
		self.get_schema_btn['state'] = 'disabled'
		
		self.combo_region['state'] = 'readonly'
		self.combo_tables['state'] = "disabled"
		self.reg_query_button['state'] = 'disabled'
		self.open_input_folder['state'] = 'disabled'

		return 0

	def user_wait(self):
		""" Displays a progressbar """

		self.progressbar = ttk.Progressbar(self.mainframe, orient=HORIZONTAL, length=200, mode='determinate')
		self.progressbar.grid(row=0, column=0)
		# self.progressbar.start()
		self.bytes = 0
		# self.max_bytes = 5000
		self.progressbar['value'] = 0
		self.progressbar['maximum'] = 5000
		self.wait = 1
		self.check_wait()

	def check_wait(self):
		""" Checks for the value of the variable wait """
		
		if self.wait == 0:
			self.progressbar.destroy()
			# self.top_win.destroy()
		else:
			self.bytes += 20
			self.progressbar['value'] = self.bytes
			self.after(100, self.check_wait)

	def get_selected_items_listbox(self):
		""" Retruns a list of selected items in a Listbox """

		# Get the index of the options selected
		listbox_selected_items = self.reg_listbox.curselection()
		listbox_items = []

		for i in listbox_selected_items:
			# Get the name of the selections in a Listbox
			listbox_items.append(self.reg_listbox.get(i))

		return listbox_items

	def retrieve_megalist(self):
		""" Connects multiple databases and updates the regression combobox """

		logger.info("Retrieving the Mega List...")

		try:
			if self.listbox_items != None:

				mega_list = get_usercolumnsel(self.selected_region, self.userinput_combo.get(), self.listbox_items)
				logger.info("Mega List retrieved : %s" % (str(mega_list), ))

			else:

				mega_list = get_usercolumnsel(self.selected_region, self.userinput_combo.get())	
				logger.info("Mega List retrieved : %s" % (str(mega_list), ))
				
		except Exception, e:

			logger.error("Error retrieving mega list - Error : %s" % (str(e), ))
			return 1

		return mega_list

		# self.fire_regression_query(mega_list)
		

	def all_user_inputs(self):
		""" Collects the user inputs and returns in the form of a list """
		
		v = self.reg_radio_picker.get()
		input_type = self.userinput_combo.get()

		dummy_list = []

		if v == "user":

			logger.info("User input selected from the radio button")

			dummy_list.append(self.userinput_entry.get())
			logger.info("Dummy list : %s" % (str(dummy_list), ))

		else:

			try:

				logger.info("Retrieving dummy list from file")
				dummy_list = retrieve_inputs_from_file(str(input_type).strip())
				logger.info("Dummy list retrieved : %s" % (str(dummy_list), ))
				
			except Exception, e:

				logger.error("Error retrieving dummy list - Error : %s" % (str(e), ))
				return 1

		return dummy_list
	

	def fire_regression_query(self):
		""" Runs the queries for regression"""

		logger.info("Regression query triggred!!....")

		# Destroying canvas and recreating one.
		self.canvas.destroy()
		self.yScrollbar.destroy()
		self.xScrollbar.destroy()
		self.canvas = Canvas(self.mainframe, background='#ffffff')
		self.canvas.grid(column=1, row=11, rowspan=6, columnspan=30, sticky=(N, E, W, S))
		self.xScrollbar = Scrollbar(self.mainframe, orient='horizontal', command=self.canvas.xview)
		self.canvas.configure(xscrollcommand=self.xScrollbar.set, width=1250)
		self.yScrollbar = Scrollbar(self.mainframe, orient='vertical', command=self.canvas.yview)
		self.canvas.configure(yscrollcommand=self.yScrollbar.set)
		self.xScrollbar.grid(column=1, row=17, columnspan=30, sticky=(N, E, W, S))
		self.yScrollbar.grid(column=31, row=11, rowspan=6, sticky=(N, E, W, S))


		# Destroying and recreating the response frame
		self.response_frame.destroy()
		self.response_frame = ttk.Frame(self.canvas, padding=(5, 0, 5, 5), height=1, width=1, relief=GROOVE, 
			borderwidth=2)
		self.canvas.create_window((4,4), window=self.response_frame, anchor="nw")
		self.response_frame.bind("<Configure>", lambda event, canvas=self.canvas : self.onFrameConfigure(canvas))
		

		# Clearing the label for last query
		logger.info("Cleared the previous query.")
		self.label_last_query.delete(1.0, END)


		# Declaring an empty list to capture all the failed validations
		fail_list = []
		empty_tables = []
		j=0

		# Get Mega list - 2D list
		mega_list = self.retrieve_megalist()

		# Retrieving all userinputs
		all_inputs = self.all_user_inputs()

		# Path for creating the result folder
		str_path = "Result\%s" % (str(time.strftime("%Y.%m.%d")), )
		logger.info("Result folder path : %s" % (str(str_path), ))

		# Current time
		str_time = time.strftime("%Y.%m.%d - %H.%M.%S")
		logger.info("Current time : %s" % (str(str_time), ))

		check_path = "%s\%s%s" % (str(str_path), str(str_time), str(".xlsx"), )
		logger.info("Check path created : %s" % (str(check_path), ))

		# Result folder and file creation
		try:
			logger.info("Creating result file...")
			file_create = create_result_file(str_path, check_path, "Result")
			logger.info("Result file created.")
			logger.info("Preparing result file...")
			write_result(check_path, "Result")
			logger.info("Result file is ready.")

		except Exception, e:
			logger.error("Result file - Error : %s" % (str(e), ))
			self.statusbar_status['text'] = "Error in Result file creation."


		self.user_wait()
		# Traversing through each user input
		for ids in all_inputs:

			logger.info("Iteration 1 : %s" % (str(ids), ))

			z = 0
			# Below validations will run only if we have something to test for the corresponding user input
			if len(mega_list) > 0:

				logger.info("Mega list is not empty.")

				flag = 0
				# Traversing through each element of the 2-D array
				for temp_region in mega_list:
					

					logger.info("Iteration 2 : %s" % (str(temp_region), ))

					# Getting all the validations requried for the current region
					valid_vals_dict = self.get_valid_dict(temp_region[1])
					logger.info("Validations to be done : %s" % (str(valid_vals_dict), ))

					k = 0
					
					# Generating the Query at runtime
					user_input = "'%s'" % (str(ids).strip(),)
					query_stmt = "SELECT * FROM %s WHERE %s=%s" % (temp_region[1], temp_region[2], user_input, )
					logger.info("Running query : %s..." % (str(query_stmt), ))

					# Executing the query for different DB connections 
					try:
						result = ibm_db.exec_immediate(self.connection_dict[temp_region[0]], query_stmt)
						logger.info("Run success!!")
					except:
						self.statusbar_status['text'] = "Not connected, Please connect to the Database again."
						logger.error("Not connected to DB. Cannot proceed.")
						return

					# Number of columns returned in the query result
					cols = ibm_db.num_fields(result)

					# Fetching the result dictionary for each row
					row = ibm_db.fetch_both(result)

					if bool(row) == False:
						empty_tables.append(temp_region[1])


					if bool(row) and flag == 0:
						j += 1

						# The name of the table for which validation is being done
						fld_name = Text(self.response_frame, background='blue', relief=GROOVE,
							borderwidth=1, font= "-size 12", foreground="white", height=1, wrap=NONE)
						val_text = str(ids)
						fld_name['width'] = len(val_text)
						fld_name.insert(1.0, val_text)

						fld_name['state'] = 'disabled'
						fld_name.grid(column=z, row=j, sticky=(W, E))
						flag = 1
						j += 1
						

					while (row):

						for i in range(0, cols):
							if k == 0:
								if i == 0:
									j += 1

									# The name of the table for which validation is being done
									fld_name = Text(self.response_frame, background='#009999', relief=GROOVE,
										borderwidth=1, font= "-size 10", foreground="white", height=1,
										wrap=NONE)
									val_text = str(temp_region[0]) + " : " + str(temp_region[1])
									fld_name['width'] = len(val_text)
									fld_name.insert(1.0, val_text)

									fld_name['state'] = 'disabled'
									fld_name.grid(column=i, row=j, sticky=(W, E))
									j += 1


								# Header of the table under validation
								fld_name = Text(self.response_frame, background='#ffaa80', relief=GROOVE,
									borderwidth=1, height=1, wrap=NONE)
								val_text = str(ibm_db.field_name(result, i))
								fld_name['width'] = len(val_text)

								fld_name.insert(1.0, val_text)
								fld_name['state'] = 'disabled'
								fld_name.grid(column=i, row=j, sticky=(W, E))

								try:

									# On successful validation
									if (self.check_vals(valid_vals_dict[ibm_db.field_name(result, i)], row[ibm_db.field_name(result, i)])) == 0:

										fld_val = Text(self.response_frame, background='green', 
											relief=GROOVE, height=1, wrap=NONE)
										val_text = str(row[ibm_db.field_name(result, i)])
										fld_val['width'] = len(val_text)

										fld_val.insert(1.0, val_text)
										fld_val['state'] = 'disabled'
										fld_val.grid(column=i, row=j + 1, sticky=(W, E))

										write_result(check_path, "Result", ids, temp_region[1], 
											valid_vals_dict[ibm_db.field_name(result, i)], row[ibm_db.field_name(result, i)], "Pass")

									else:

										# On unsuccessful validation
										fld_val = Text(self.response_frame, background='red',
											relief=GROOVE, height=1, wrap=NONE)
										val_text = str(row[ibm_db.field_name(result, i)])
										fld_val['width'] = len(val_text)

										fld_val.insert(1.0, val_text)
										fld_val['state'] = 'disabled'
										fld_val.grid(column=i, row=j + 1, sticky=(W, E))
										fail_list.append([temp_region[1], ibm_db.field_name(result, i)])

										write_result(check_path, "Result", ids, temp_region[1], 
											valid_vals_dict[ibm_db.field_name(result, i)], row[ibm_db.field_name(result, i)], "Fail")

								# When the column being validated is not in the list of columns to be validated
								except KeyError:

									fld_val = Text(self.response_frame, relief=GROOVE, height=1,
										wrap=NONE)
									val_text = str(row[ibm_db.field_name(result, i)])
									fld_val['width'] = len(val_text)

									fld_val.insert(1.0, val_text)
									fld_val['state'] = 'disabled'
									fld_val.grid(column=i, row=j + 1, sticky=(W, E))


									if i == (cols - 1):
										j += 1
							else:

								try:
									
									# On successful validation
									if (self.check_vals(valid_vals_dict[ibm_db.field_name(result, i)], row[ibm_db.field_name(result, i)])) == 0:

										fld_val = Text(self.response_frame, background='green',
											relief=GROOVE, height=1, wrap=NONE)
										val_text = str(row[ibm_db.field_name(result, i)])
										fld_val['width'] = len(val_text)

										fld_val.insert(1.0, val_text)
										fld_val['state'] = 'disabled'
										fld_val.grid(column=i, row=j + 1, sticky=(W, E))

										write_result(check_path, "Result", ids, temp_region[1], 
											valid_vals_dict[ibm_db.field_name(result, i)], row[ibm_db.field_name(result, i)], "Pass")


									else:
										# On unsuccessful validation
										fld_val = Text(self.response_frame, background='red',
											relief=GROOVE, height=1, wrap=NONE)
										val_text = str(row[ibm_db.field_name(result, i)])
										fld_val['width'] = len(val_text)

										fld_val.insert(1.0, val_text)
										fld_val['state'] = 'disabled'
										fld_val.grid(column=i, row=j + 1, sticky=(W, E))

										write_result(check_path, "Result", ids, temp_region[1], 
											valid_vals_dict[ibm_db.field_name(result, i)], row[ibm_db.field_name(result, i)], "Fail")

										fail_list.append([temp_region[1], ibm_db.field_name(result, i)])
								
								# When the column being validated is not in the list of columns to be validated
								except KeyError:

									fld_val = Text(self.response_frame, relief=GROOVE, height=1,
										wrap=NONE)
									val_text = str(row[ibm_db.field_name(result, i)])
									fld_val['width'] = len(val_text)
									fld_val.insert(1.0, val_text)

									fld_val['state'] = 'disabled'
									fld_val.grid(column=i, row=j + 1, sticky=(W, E))


						k = 1
						# Fetching new row from database
						row = ibm_db.fetch_both(result)
						j += 1
					

					# Checking if any validation failed
					self.label_last_query['state'] = 'normal'
					self.label_last_query.delete(1.0, END)

					if len(fail_list) > 0:
						self.label_last_query['foreground'] = "red"
						self.label_last_query.insert(1.0, "%d validations failed." % (len(fail_list), ))

						if len(empty_tables) != 0: self.label_last_query.insert(END, "\nThese tables did not retrun any records - %s" % str(empty_tables) )
						
						logger.info("Validations failed : %s" % (str(fail_list), ))
					elif j == 0:
						self.label_last_query['foreground'] = "black"
						self.label_last_query.insert(1.0, "No Records returned.", )
						
						logger.info("No records returned.")
					elif len(empty_tables) != 0:
						self.label_last_query['foreground'] = "red"
						self.label_last_query.insert(END, "These tables did not retrun any records - %s\n" % str(empty_tables) )
						logger.info("These tables did not retrun any records - %s\n" % str(empty_tables))
					else:
						self.label_last_query['foreground'] = "#00cc00"
						self.label_last_query.insert(1.0, "Pass", )
						
						logger.info("Result : Pass")
					self.label_last_query['state'] = 'disabled'

					# TO be updated
					# self.statusbar_status['text'] = "Query returned %d row(s)." % (j,)
					
					
			else:
				self.statusbar_status['text'] = "No tables with the selected Regression - User Column Selection"
				logger.warn("Please make sure that the tables mentioned in the Excel sheet has the Input Parameter mentioned.")
			z += 1
		self.wait = 0


	def db_connect_reg(self, region=None):
		""" Regression : Connects to the region given in the argument and returns the connection object """

		listbox_items = self.get_selected_items_listbox()
		self.listbox_items = listbox_items

		if len(self.listbox_items) == 0:
			tkMessageBox.showinfo("Info", "Please select a region from the listbox, and then click on Connect.")
			return
		

		# Connect to each selected region
		for region in listbox_items:
			temp_config = get_config(region)
			con_str = "Database=%s;HOSTNAME=%s;PORT=%s;PROTOCOL=%s;UID=%s;PWD=%s;" % (str(temp_config[3]).strip(), str(temp_config[1]).strip(),
				str(temp_config[2]).strip(), "TCPIP", str(temp_config[4]).strip(), str(temp_config[5]).strip(),)

			try:
				temp_conn = ibm_db.connect(con_str, "", "")
				self.statusbar_status['text'] = "Connected to %s." % (region, )
			except:
				self.statusbar_status['text'] = "Connection to %s failed" % (region,)
				return 1

			self.statusbar_status['text'] = "Connected to %s" % (listbox_items, )
			self.connection_dict[region] = temp_conn

			self.reg_listbox.config(state = DISABLED)

			self.reg_button_connect['state'] = 'disabled'
			self.reg_button_disconnect['state'] = 'normal'
		# Returns a list of all DB connection objects 


		return 0

	def db_disconnect_reg(self, conn_obj=None):
		"""  Disconnects all Regression DB connections """

		# Get a list of selected items

		if self.listbox_items != None:

			j = 1
			for conn_obj in self.listbox_items:
				if self.connection_dict[conn_obj]:
					try:
						ibm_db.close(self.connection_dict[conn_obj])
						self.statusbar_status['text'] = "Connection Closed!!"
					except:
						err = ibm_db.conn_errormsg()
						self.statusbar_status['text'] = "Connection is closed already!! :)"
						return 1
				j += 1

			self.statusbar_status['text'] = "%d connections closed." % (j - 1, )

			self.reg_listbox.config(state = NORMAL)
			self.listbox_items = None

			self.reg_button_connect['state'] = 'normal'
			self.reg_button_disconnect['state'] = 'disabled'

		return 0



	def get_listbox_list(self, selected_flag):
		""" Returns a list of sub databases (FICS, Trans Repo and Notif Repo) for a selected primary database """

		listbox_list = []

		if selected_flag == "test1" or selected_flag == "prod1" or selected_flag == "stage1":
			listbox_list = get_sub_regions(selected_flag)
			
		else:
			
			listbox_list.append("Please use Run a Query tab.")

		return sorted(listbox_list)


	def update_listbox(self, selected_flag):
		""" Updates Listbox """

		sub_region_list = self.get_listbox_list(selected_flag)

		# Clear the listbox
		self.reg_listbox.delete(0, END)

		for i in sub_region_list:
			self.reg_listbox.insert(0, i)

		return sub_region_list

	def get_tables(self, tableName):
		""" Updates the Table ComboBox by fetching the table names from the Excel Sheet """

		# Fetching the tables from the excel
		all_tables = fetch_table_names(self.combo_region.get())

		# Updating the tables combobox 
		tableName['values'] = all_tables

		# Selecting the first option
		tableName.current(0)
		tableName.event_generate('<<ComboboxSelected>>')

		return all_tables

	def get_valid_dict(self, table_name):
		""" Returns the Column Name and Values for validation from the Excel sheet"""

		logger.info("-- Getting Valid Dict --")
		# Retrieve dict with column name and its expected value
		try:
			validation_dict = get_validations(table_name)
			logger.info("Validations retrieved : %s" % (str(validation_dict), ))
		except Exception, e:
			logger.error("Error retrieving validations from Excel - Error : %s" % (str(e), ))

		return validation_dict

	def create_query_widget(self):
		""" Create widgets for Query Frame """

		logger.info("-- Create Query Widget --")
		# Retrieving input parameter names from the excel sheet

		try:
			self.input_params = get_input_params(self.combo_region.get(), self.combo_tables.get())
			logger.info("Input params retreieved : %s" % (str(self.input_params), ))
		except Exception, e:
			logger.error("Error creating widgets. Error - %s" % (str(e), ))
			self.statusbar_status['value'] = "Error - check logs."

		# Checks if the query frame exists
		if self.query_frame.winfo_exists():
			self.query_frame.destroy()
		# Creating a frame at run-time and updating its widgets
		# Creates a new frame
		
		self.query_frame = ttk.Frame(self.query_canvas, height=2, width=2, padding=(5, 3, 5, 5))
		self.query_canvas.create_window((4,4), window=self.query_frame, anchor="nw")
		self.query_frame.bind("<Configure>", lambda event, canvas=self.query_canvas : self.onFrameConfigure(canvas))

		return 0


	def table_change(self, event):
		""" Updates the frame on change of the table name """

		logger.info("-- Table Change -- ")
		# Create query form widget
		self.create_query_widget()

		# Declaring dictionaries for the labels and entries
		self.labels = {}
		self.entry = {}

		# Traversing through each parameter
		i = 0
		for params in self.input_params:

			# Creating a Label for each parameter
			l = ttk.Label(self.query_frame, text= params + " : ")
			l.grid(column=0, row=i, sticky=(W, E))
			self.labels[params] = l

			# Creating an Entry for each parameter
			e = ttk.Entry(self.query_frame, width=25)
			e.grid(column=1, row=i, columnspan=2, sticky=(W, E))
			self.entry[params] = e
			i += 1

		if i > 0:
			# Order by Label
			self.order_by = ttk.Label(self.query_frame, text="ORDER BY : ")
			self.order_by.grid(column=0, row=i, sticky=(W, E))

			# Order by ComboBox
			self.order_by_combo = ttk.Combobox(self.query_frame, state="readonly")
			self.order_by_combo.grid(column=1, row=i, sticky=(W, E))

			col_list = self.get_column_names(self.combo_tables.get())

			self.order_by_combo['values'] = col_list
			self.order_by_combo.current(0)

			# Max row Label
			self.max_row = ttk.Label(self.query_frame, text="MAX ROW : ")
			self.max_row.grid(column=0, row=i + 1, sticky=(W, E))

			# Max row combobox
			self.max_row_combo = ttk.Combobox(self.query_frame, state="readonly")
			self.max_row_combo.grid(column=1, row=i + 1, sticky=(W, E))

			self.max_row_combo['values'] = [5, 10, 20]
			self.max_row_combo.current(0)


			# Creating a query button

			self.query_btn = ttk.Button(self.query_frame, text="Query", command=partial(self.query_splitter, "query_btn"))
			self.query_btn.grid(column=0, row=i + 2, sticky=(W, E))


		return 0

	def get_query(self):
		""" Builds a query statement with table name and input parameters """


		logger.info("-- Get Query --")
		# Getting the number of input parameters
		num_of_params = len(self.input_params)


		var_str = ""

		# iterating and building a input param statement
		for i in range(0, (num_of_params)):

			# Check if the user has entered a value
			if self.entry[self.input_params[i]].get().strip() != "":
				if i == (num_of_params - 1):
					var_str += "%s = '%s'" % (self.input_params[i].strip(),self.entry[self.input_params[i]].get().strip(), )

					break

				elif i < (num_of_params - 1):
					var_str += "%s = '%s' AND " % (self.input_params[i].strip(), self.entry[self.input_params[i]].get().strip(), )

				else:
					pass

		if var_str.strip()[-3:] == "AND":
			var_str = var_str.strip()[:-4]

		if var_str.strip() != "":
		# Final query building with table name

			final_query = "SELECT * FROM %s WHERE %s ORDER BY %s DESC FETCH FIRST %d ROW ONLY;" % (self.combo_tables.get().strip(), 
				var_str.strip(), self.order_by_combo.get().strip(), int(self.max_row_combo.get().strip()), )
		else:
			final_query = "SELECT * FROM %s ORDER BY %s DESC FETCH FIRST %d ROW ONLY;" % (self.combo_tables.get().strip(), 
				self.order_by_combo.get().strip(), int(self.max_row_combo.get().strip()), )

		logger.info("Final Query : %s" % (str(final_query), ))
		return final_query

	def get_column_names(self, selected_table):
		""" Retrieves the names of the Column of a table """

		# Table names to be updated in the Order By combo box
		self.table_column_name = []

		# Checks if the connection is open
		if self.conn:

			# Buils the query with just the selected table name and without schema
			split_table = selected_table.split(".")

			schname = "'%s'" % str(split_table[0])
			tbname = "'%s'" % (split_table[1].strip(),)

			query_stmt = "SELECT COLNAME FROM SYSCAT.COLUMNS WHERE TABSCHEMA=%s AND TABNAME=%s;" % (schname, tbname, )
			result = ibm_db.exec_immediate(self.conn, query_stmt)

			# Fetches the result dictionary
			row = ibm_db.fetch_both(result)
			
			# Runs the loop till the time row has a value
			while(row):
				self.table_column_name.append(str(row[ibm_db.field_name(result, 0)]).strip())
				row = ibm_db.fetch_both(result)
				
		# Returns the list of Tables column names
		return self.table_column_name

	def query_splitter(self, source):
		""" Creates a query and triggers it by identifying the correct source """


		if source == "query_btn":

			logger.info("Run a Query : Query button clicked.")
			query_stmt = self.get_query()
			logger.info("Query created : %s" % (str(query_stmt), ))

			self.fire_query(query_stmt)
						

		elif source == "get_schema_btn":

			logger.info("Get Schema clicked.")
			tbname = "'%s'" % (self.combo_tables.get().split(".")[1].strip(),)
			query_stmt = "SELECT COLNAME FROM SYSCAT.COLUMNS WHERE TABNAME=%s;" % (tbname, )
			logger.info("Query created : %s" % (str(query_stmt), ))
			self.fire_schema(query_stmt)


	def check_vals(self, valid_vals, actual_val):
		""" Cross checks for the availability of actual_val val in valid_vals and returns 0 or 1 """

		k = 1

		# checking among each value of valid values
		for val in valid_vals:
			if str(actual_val).strip().upper() == str(val).strip().upper():
				k = 0
				return k

		return k

	def fire_schema(self, query_stmt):
		""" Retrieves the query from the get_query() method and fires the query to Database """

		# Displaying the query statement
		
		self.label_last_query['state'] = 'normal'
		self.label_last_query.delete(1.0, END)
		self.label_last_query['foreground'] = 'grey'
		self.label_last_query.insert(1.0, str(query_stmt))
		self.label_last_query['state'] = 'disabled'
		
		self.canvas.destroy()
		self.yScrollbar.destroy()
		self.xScrollbar.destroy()

		try:
			logger.info("Running query : %s" % (str(query_stmt), ))
			result = ibm_db.exec_immediate(self.conn, query_stmt)
			logger.info("Query run success!!")
		except Exception, e:
			self.statusbar_status['text'] = "Some issue with query structure. Please check logs."
			logger.error("Error running query - %s" % (str(e), ))
			return 1

		# Number of columns returned as a query result
		cols = ibm_db.num_fields(result)


		# Destroying canvas and recreating one.


		self.canvas = Canvas(self.mainframe, background='#ffffff')
		self.canvas.grid(column=1, row=11, rowspan=6, columnspan=30, sticky=(N, E, W, S))
		self.xScrollbar = Scrollbar(self.mainframe, orient='horizontal', command=self.canvas.xview)
		self.canvas.configure(xscrollcommand=self.xScrollbar.set, width=1250)
		self.yScrollbar = Scrollbar(self.mainframe, orient='vertical', command=self.canvas.yview)
		self.canvas.configure(yscrollcommand=self.yScrollbar.set)

		self.xScrollbar.grid(column=1, row=17, columnspan=30, sticky=(N, E, W, S))
		self.yScrollbar.grid(column=31, row=11, rowspan=6, sticky=(N, E, W, S))

		# Destroying the frame and re-creating one
		self.response_frame.destroy()
		self.response_frame = ttk.Frame(self.canvas, padding=(5, 0, 5, 5), height=1, width=1, relief=GROOVE, 
		borderwidth=2)
		self.canvas.create_window((4,4), window=self.response_frame, anchor="nw")
		self.response_frame.bind("<Configure>", lambda event, canvas=self.canvas : self.onFrameConfigure(canvas))

		# Row dictionary fetched from the IBM DB2
		row = ibm_db.fetch_both(result)

		
		j=0
		while (row):
			logger.info("Entering row : %s" % (str(j), ))
			# Traversing through each column
			for i in range(0, cols):
				if j == 0:

					# Displaying the table headers
					fld_name = Text(self.response_frame, background='yellow', relief=GROOVE,
						borderwidth=1, height=1, width=20)
					fld_name.insert(1.0, ibm_db.field_name(result, i))
					fld_name['state'] = 'disabled'
					fld_name.grid(column=i, row=j, sticky=(W, E))
					logger.info("Header Printed.")

					# Displaying 1st row

					fld_val = Text(self.response_frame, height=1, width=20)
					fld_val.insert(1.0, str(row[ibm_db.field_name(result, i)]))
					fld_val['state'] = 'disabled'
					fld_val.grid(column=i, row=j + 1, sticky=(W, E))
					logger.info("First row printed.")
				else:

					fld_val = Text(self.response_frame, height=1, width=20)
					fld_val.insert(1.0, str(row[ibm_db.field_name(result, i)]))
					fld_val['state'] = 'disabled'
					fld_val.grid(column=i, row=j + 1, sticky=(W, E))
					


			# Fetches the next dict from the database
			row = ibm_db.fetch_both(result)
			
			
			j += 1

		logger.info("%s rows retrieved." % str(j))
		self.statusbar_status['text'] = "Query returned %d row(s)." % (j,)

	def waq_fire_query(self):
		""" Manipulates the waq_final_stmt and hands over the statement to fire_query """
		
		# self.waq_text.insert(END, ";")
		user_query = self.waq_text.get(1.0, END).replace("\n", "")

		if user_query[-1] != ";":
			user_query = '%s;' % user_query

		first_query = user_query[0:user_query.index(";") + 1]

		
		# user_query_one = user_query.split("FETCH FIRST ")[0]
		split_user_query = first_query.split("FETCH FIRST ")

		if len(split_user_query) > 1:

			second_split = split_user_query[1].split(" ")

			if int(second_split[0]) > 50:

				final_query = '%s FETCH FIRST %s ROW ONLY;' % (split_user_query[0], 50, )
			else:

				final_query = first_query

		else:

			final_query = '%s FETCH FIRST %s ROW ONLY;' % (user_query[0:user_query.index(";")], 5, ) 

		
		self.label_last_query['state'] = 'normal'
		self.label_last_query.delete(1.0, END)
		self.label_last_query.insert(1.0, final_query)
		self.label_last_query['state'] = 'disabled'

		self.fire_query(final_query)


	def fire_query(self, query_stmt, flag=None):
		""" Retrieves the query from the get_query() method and fires the query to Database """

		# Retrieving the values to be validated
		valid_vals_dict = self.get_valid_dict(self.combo_tables.get())

		logger.info("Validation values retrieved from excel : %s" % (str(valid_vals_dict), ))
		
		
		try:
			logger.info("Running query : %s" % (str(query_stmt), ))
			result = ibm_db.exec_immediate(self.conn, query_stmt)
			logger.info("Query run success!!")
		except Exception, e:
			self.statusbar_status['text'] = "Some issue with query structure. Please check logs."
			logger.error("Error running query - %s" % (str(e), ))
			return 1

		# Number of columns returned as a query result
		cols = ibm_db.num_fields(result)
		

		# Destroying canvas and recreating one.

		self.canvas.destroy()
		self.yScrollbar.destroy()
		self.xScrollbar.destroy()
		self.canvas = Canvas(self.mainframe, background='#ffffff')
		self.canvas.grid(column=1, row=11, rowspan=6, columnspan=30, sticky=(N, E, W, S))
		self.xScrollbar = Scrollbar(self.mainframe, orient='horizontal', command=self.canvas.xview)
		self.canvas.configure(xscrollcommand=self.xScrollbar.set, width=1250)
		self.yScrollbar = Scrollbar(self.mainframe, orient='vertical', command=self.canvas.yview)
		self.canvas.configure(yscrollcommand=self.yScrollbar.set)

		self.xScrollbar.grid(column=1, row=17, columnspan=30, sticky=(N, E, W, S))
		self.yScrollbar.grid(column=31, row=11, rowspan=6, sticky=(N, E, W, S))

		# Destroying the frame and re-creating one
		self.response_frame.destroy()
		self.response_frame = ttk.Frame(self.canvas, padding=(5, 0, 5, 5), height=1, width=1, relief=GROOVE, 
		borderwidth=2)
		self.canvas.create_window((4,4), window=self.response_frame, anchor="nw")
		self.response_frame.bind("<Configure>", lambda event, canvas=self.canvas : self.onFrameConfigure(canvas))

		# Displaying the query statement
		self.label_last_query['state'] = 'normal'
		self.label_last_query.delete(1.0, END)
		self.label_last_query['foreground'] = 'grey'
		self.label_last_query.insert(1.0, str(query_stmt))
		self.label_last_query['state'] = 'disabled'

		# Row dictionary fetched from the IBM DB2
		row = ibm_db.fetch_both(result)

		# self.noOfRecords = 0
		
		j=0
		while (row):
			logger.info("Entering row : %s" % (str(j), ))
			# Traversing through each column
			for i in range(0, cols):
				if j == 0:

					# Displaying the table headers
					fld_name = Text(self.response_frame, background='yellow', relief=GROOVE,
						borderwidth=1, height=1)
					val_text = str(ibm_db.field_name(result, i))
					fld_name.configure(width=len(val_text) + 5)

					fld_name.insert(1.0, val_text)
					fld_name['state'] = 'disabled'
					fld_name.grid(column=i, row=j, sticky=(W, E))

					try:
						# checks if the value returned is present in the expected values
						if self.check_vals(valid_vals_dict[ibm_db.field_name(result, i)], row[ibm_db.field_name(result, i)]) == 0:

							fld_val = Text(self.response_frame, background='green', height=1)
							val_text = str(row[ibm_db.field_name(result, i)]).strip()
							fld_val.configure(width=len(val_text) + 5)
							
							fld_val.insert(1.0, val_text)							
							fld_val['state'] = 'disabled'
							fld_val.grid(column=i, row=j + 1, sticky=(W, E))
							logger.info("Pass")
							

						else:

							fld_val = Text(self.response_frame, background='red', height=1)
							val_text = str(row[ibm_db.field_name(result, i)]).strip()
							fld_val.configure(width = len(val_text) + 5)
							
							fld_val.insert(1.0, val_text)
							
							fld_val['state'] = 'disabled'
							fld_val.grid(column=i, row=j + 1, sticky=(W, E))
							logger.info("Fail")
							
							

					# When the column value is not to be tested
					except KeyError:

						fld_val = Text(self.response_frame, height=1)
						val_text=str(row[ibm_db.field_name(result, i)]).strip()
						fld_val.configure(width = len(val_text) + 5)
						fld_val.insert(1.0, val_text)
						
						fld_val['state'] = 'disabled'
						fld_val.grid(column=i, row=j + 1, sticky=(W, E))
						

				else:

					# For rows other than the first row, that is returned from the database
					try:
						
						# checks if the value returned is present in the expected values
						if self.check_vals(valid_vals_dict[ibm_db.field_name(result, i)], row[ibm_db.field_name(result, i)]) == 0:

							fld_val = Text(self.response_frame, background='green', height=1)
							val_text = str(row[ibm_db.field_name(result, i)]).strip()
							fld_val.configure(width = len(val_text) + 5)
							fld_val.insert(1.0, val_text)
							
							fld_val['state'] = 'disabled'
							fld_val.grid(column=i, row=j + 1, sticky=(W, E))
							logger.info("Pass")
							

						else:

							fld_val = Text(self.response_frame, background='red', height=1)
							val_text=str(row[ibm_db.field_name(result, i)]).strip()
							fld_val.configure(width = len(val_text) + 5)
							fld_val.insert(1.0, val_text)
							
							fld_val['state'] = 'disabled'
							fld_val.grid(column=i, row=j + 1, sticky=(W, E))
							logger.info("Fail")
							
							
							
					# When the column value is not to be tested
					except KeyError:

						fld_val = Text(self.response_frame, height=1)
						val_text = str(row[ibm_db.field_name(result, i)]).strip()
						fld_val.configure(width = len(val_text) + 5)
						fld_val.insert(1.0, val_text)
						
						fld_val['state'] = 'disabled'
						fld_val.grid(column=i, row=j + 1, sticky=(W, E))
						


			# Fetches the next dict from the database
			row = ibm_db.fetch_both(result)

			j += 1

		
		self.statusbar_status['text'] = "Query returned %d row(s)." % (j,)

	def waq_table_change(self, event):
		""" Responds to Write a Query Table change """

		# Retreive Column names

		waq_columns = self.get_column_names(self.waq_combo_tables.get())

		cols_stmt = waq_columns[0]

		for i in range(1, len(waq_columns) - 1):

			cols_stmt = '%s, %s' % (cols_stmt, waq_columns[i], ) 
			# print waq_columns[i]
			
		cols_stmt = '%s, %s' % (cols_stmt, waq_columns[len(waq_columns) - 1], ) 

		waq_final_query = 'SELECT %s FROM %s FETCH FIRST 5 ROW ONLY;' % (cols_stmt, self.waq_combo_tables.get(), )

		self.waq_text.delete(1.0, END)
		self.waq_text.insert(END, waq_final_query)

	def openFolder(self):
		""" Opens the input file folder """
		
		# Get current working directory
		l = os.getcwd()

		# Append the input folder name in the string
		l = "%s%s" % (str(l), "\Input", )

		# Create the final string
		l = '%s %s' % ("explorer", l, )
		
		# Open the folder in the Windows explorer
		subprocess.Popen(l)


	def toggle_widget(self, selected_widget, status):
		""" It will Enable or Disable the widget """

		if str(status) == 'enable':
			selected_widget['state'] = 'normal'
		else:
			selected_widget['state'] = 'disabled'

	def contactus(self):
		""" Contact Us option in Menubar """

		tkMessageBox.showinfo("Contact Us", "Mohd Ejaz Siddiqui - mejaz_siddiqui@optum.com\n Vaibhav Rawat - vaibhav_rawat@optum.com")

	def onFrameConfigure(self, canvas):
	    '''Reset the scroll region to encompass the inner frame'''

	    canvas.configure(scrollregion=canvas.bbox("all"))

	def createWidget(self, master):
		""" Creates all the widgets """


		# Application window title
		master.title("Database Checker - v2.0")
		master.iconbitmap(default='db.ico')


		# All frames
		# Main frame
		self.mainframe = ttk.Frame(master, padding=(5, 10, 5, 3))
		self.mainframe.grid(column=0, row=0, sticky=(N, E, W, S))


		# Button franes
		self.buttonFrame = ttk.Frame(self.mainframe)
		self.buttonFrame.grid(column=2, row=8, sticky=(W, E))

		# Notebook
		self.nb = ttk.Notebook(self.mainframe, padding=(10, 0, 0, 0))
		self.nb.grid(column=3, row=1, columnspan=28, rowspan=8, sticky=(E, N, W, S))
		self.reg_frame = ttk.Frame(self.nb, padding=(5, 7, 5, 5))

		# Listbox for regression
		self.listbox_items = None
		self.reg_listbox = Listbox(self.reg_frame, selectmode='multiple', height=3, width=50, activestyle='none')
		self.reg_frame.grid(column=0, row=0, columnspan=3, rowspan=4, sticky=(E, N, W, S))
		self.nb.add(self.reg_frame, text="Regression")


		# Query Frame
		self.query_frame_master = ttk.Frame(self.nb)
		self.query_canvas = Canvas(self.query_frame_master)
		self.query_canvas.configure(width=390, height=140)
		self.query_canvas.grid(row=2, column=0, rowspan=5, columnspan=4, sticky=(E, N, W, S))
		self.nb.add(self.query_frame_master, text="Run a Query")
		self.query_frame = ttk.Frame(self.query_canvas, height=2, width=2, padding=(5, 0, 5, 5))

		# Write a query frame
		self.writeAQueryFrame = ttk.Frame(self.nb)
		self.nb.add(self.writeAQueryFrame, text="Write a Query")

		self.waq_table_frame = ttk.Frame(self.writeAQueryFrame, padding=(10, 10, 5, 20))
		self.waq_table_frame.grid(column=0, row=0, columnspan=30, sticky=(W, E))

		# frame 2
		self.activity_frame = ttk.Frame(self.query_frame_master, padding=(10, 10, 5, 20))
		self.activity_frame.grid(column=0, row=0, columnspan=30, sticky=(W, E))


		# Menu bar
		self.menubar = Menu()

		# First Menu
		menu = Menu(self.menubar, tearoff=0)
		self.menubar.add_cascade(label="File", menu=menu)
		menu.add_command(label="Close", command=self.quit)

		# Second Menu
		menu = Menu(self.menubar, tearoff=0)
		self.menubar.add_cascade(label="Help", menu=menu)
		menu.add_command(label="Contact Us", command=self.contactus)
		self.master.config(menu=self.menubar)

		# response frame
		# Response Canvas

		self.canvas = Canvas(self.mainframe, background='#ffffff')
		self.response_frame = ttk.Frame(self.canvas, padding=(5, 0, 5, 5), relief=GROOVE, 
			borderwidth=2)
		self.canvas.grid(column=1, row=11, rowspan=6, columnspan=30, sticky=(N, E, W, S))

		#----------- Horizontal - Scrollbar -----------
		self.xScrollbar = Scrollbar(self.mainframe, orient='horizontal', command=self.canvas.xview)
		self.canvas.configure(xscrollcommand=self.xScrollbar.set, width=1250)

		self.xScrollbar.grid(column=1, row=17, columnspan=30, sticky=(N, E, W, S))

		#----------- Vertical - Scrollbar : Response Frame-----------

		self.yScrollbar = Scrollbar(self.mainframe, orient='vertical', command=self.canvas.yview)
		self.canvas.configure(yscrollcommand=self.yScrollbar.set)

		self.yScrollbar.grid(column=31, row=11, rowspan=6, sticky=(N, E, W, S))

		#----------- Vertical - Scrollbar : Query Frame-----------

		self.yQScrollbar = Scrollbar(self.query_frame_master, orient='vertical', command=self.query_canvas.yview)
		self.query_canvas.configure(yscrollcommand=self.yQScrollbar.set)

		self.yQScrollbar.grid(column=4, row=0, rowspan=8, sticky=(N, E, W, S))

		self.query_canvas.create_window((4,4), window=self.query_frame, anchor="nw")
		self.query_frame.bind("<Configure>", lambda event, canvas=self.query_canvas : self.onFrameConfigure(canvas))

		#------------ End Scrollbar ------------------

		self.canvas.create_window((4,4), window=self.response_frame, anchor="nw")
		self.response_frame.bind("<Configure>", lambda event, canvas=self.canvas : self.onFrameConfigure(canvas))

		# End Canvas

		# Separator
		self.ver_sep = ttk.Separator(self.mainframe, orient=VERTICAL)
		self.hor_sep = ttk.Separator(self.mainframe, orient=HORIZONTAL)
		self.hor_sep2 = ttk.Separator(self.mainframe, orient=HORIZONTAL)

		# All Labels
		self.label_regions = ttk.Label(self.mainframe, text="Region : ")
		self.label_databases = ttk.Label(self.mainframe, text="Database : ")
		self.label_tables = ttk.Label(self.activity_frame, text="Table : ")
		self.waq_label_tables = ttk.Label(self.waq_table_frame, text="Table : ")
		self.label_username = ttk.Label(self.mainframe, text="Username : ")
		self.label_password = ttk.Label(self.mainframe, text="Password : ")
		self.label_blank1 = ttk.Label(self.mainframe, text="")
		self.label_blank2 = ttk.Label(self.mainframe, text="")
		# self.progressbar = ttk.Progressbar(self.mainframe, orient='horizontal', length=200, mode='determinate')
		self.label_response = ttk.Label(self.mainframe, text="Response : ", font="-weight bold")
		self.label_last_query = Text(self.mainframe, foreground='black', font=('Courier New', 10), relief=FLAT, background='#f2f2f2',
			state='disabled', height=2, width=140)
		self.statusbar_parent = ttk.Label(self.mainframe, text="")
		self.statusbar_label = ttk.Label(self.statusbar_parent, text="Status :")
		self.statusbar_status = ttk.Label(self.statusbar_parent, text="", wraplength=600)
		self.reg_userinput = ttk.Label(self.reg_frame, text="Input Parameter : ")

		# All Entries
		self.db_val = StringVar()
		self.username = StringVar()
		self.password = StringVar()
		self.entry_database = ttk.Entry(self.mainframe, textvariable=self.db_val, state="readonly")
		self.entry_username = ttk.Entry(self.mainframe, textvariable=self.username)
		self.entry_password = ttk.Entry(self.mainframe, textvariable=self.password, show='*')
		self.userinput_entry = ttk.Entry(self.reg_frame)

		# All Combo Boxes
		self.region_vals = StringVar()
		self.combo_region = ttk.Combobox(self.mainframe, textvariable=self.region_vals, state="readonly")

		self.combo_tables = ttk.Combobox(self.activity_frame, width=40, state=DISABLED)
		self.waq_combo_tables = ttk.Combobox(self.waq_table_frame, width=40, state="readonly")
		self.userinput_combo = ttk.Combobox(self.reg_frame, state="readonly")
		

		# All Radio Buttons
		self.reg_radio_picker = StringVar()
		self.reg_radio_picker.set("user")
		self.userinput_radio = ttk.Radiobutton(self.reg_frame, text="From Textbox", value="user", variable=self.reg_radio_picker)
		self.userinput_radio['command'] = partial(self.toggle_widget, self.userinput_entry, 'enable')
		self.fileinput_radio = ttk.Radiobutton(self.reg_frame, text="From File", value="file", variable=self.reg_radio_picker)
		self.fileinput_radio['command'] = partial(self.toggle_widget, self.userinput_entry, 'disable')
		
		# All Buttons
		self.connect_button = ttk.Button(self.buttonFrame, text="Connect", command=self.db_connect)
		self.disconnect_button = ttk.Button(self.buttonFrame, text="Disconnect", command=self.db_disconnect, state=DISABLED)
		self.reg_button_connect	= ttk.Button(self.reg_frame, text="Connect", command=self.db_connect_reg, state=DISABLED)
		self.reg_button_disconnect	= ttk.Button(self.reg_frame, text="Disconnect", command=self.db_disconnect_reg, state=DISABLED)
		self.reg_query_button = ttk.Button(self.reg_frame, text="Query", command=self.fire_regression_query, state=DISABLED)
		self.get_schema_btn = ttk.Button(self.activity_frame, text="Get Schema", state=DISABLED, 
			command=partial(self.query_splitter, "get_schema_btn"))
		self.open_input_folder = ttk.Button(self.reg_frame, text="Open Input Folder", command=self.openFolder, width=18)
		self.waq_queryButton = ttk.Button(self.writeAQueryFrame, text="Run", command=self.waq_fire_query)

		# WAQ Text Widget
		self.waq_text = Text(self.writeAQueryFrame, height=6, width=100)
		self.waq_text.grid(row=2, column=1, rowspan=6, sticky=(E, W), pady=(5, 5), padx=(50, 5))
		
			
		# Positioning in the mainframe - Labels
		self.label_regions.grid(column=1, row=1, sticky=(W, E))
		self.label_databases.grid(column=1, row=3, sticky=(W, E))
		self.label_tables.grid(column=0, row=1, sticky=(W, E))
		self.waq_label_tables.grid(column=0, row=1, sticky=(W, E))
		self.label_username.grid(column=1, row=4, sticky=(W, E))
		self.label_password.grid(column=1, row=5, sticky=(W, E))
		self.label_blank1.grid(column=1, row=6, sticky=(W, E))
		self.label_blank2.grid(column=1, row=7, sticky=(W, E))
		# self.progressbar.grid(column=1, row=7, sticky=(W, E))
		self.label_response.grid(column=1, row=10, sticky=(W, E), pady=(2, 5))
		self.label_last_query.grid(column=2, row=10, columnspan=28, sticky=(W, E), pady=(2, 5))
		self.statusbar_parent.grid(column=1, row=18, columnspan=29, sticky=(W, E))
		self.statusbar_label.grid(column=1, row=1, sticky=(W, E))
		self.statusbar_status.grid(column=2, row=1, columnspan=29, sticky=(W, E))


		# Positioning in the mainframe - ComboBox
		self.combo_region.grid(column=2, row=1, sticky=(W, E))
		self.combo_tables.grid(column=1, row=1, sticky=(W, E))
		self.waq_combo_tables.grid(column=1, row=1, sticky=(W))

		# Positioning in the mainframe - Entries
		self.entry_database.grid(column=2, row=3, sticky=(W, E))
		self.entry_username.grid(column=2, row=4, sticky=(W, E))
		self.entry_password.grid(column=2, row=5, sticky=(W, E))

		# Positioning in the mainframe - Buttons

		self.disconnect_button.grid(column=0, row=0, sticky=(W, E))
		self.connect_button.grid(column=1, row=0, sticky=(W, E))
		self.waq_queryButton.grid(column=1, row=8, sticky=(W), pady=(10, 10), padx=(50, 0))
		# self.get_schema_btn.grid(column=3, row=1, sticky=(W, E))

		# Positioning in the regression frame
		
		self.reg_listbox.grid(column=0, row=0, rowspan=2, columnspan=2, sticky=(W, E))
		self.reg_button_connect.grid(column=2, row=0, sticky=(W, E), padx=(5, 5))
		self.reg_button_disconnect.grid(column=2, row=1, sticky=(W, E), padx=(5, 5))
		self.reg_userinput.grid(column=0, row=2, sticky=(W, E))
		self.userinput_combo.grid(column=1, row=2, sticky=(W, E))
		self.userinput_entry.grid(column=1, row=3, sticky=(W, E))
		self.reg_query_button.grid(column=2, row=4, sticky=(W, E), pady=(5, 5))
		self.userinput_radio.grid(column=0, row=3, sticky=(W, E))
		self.fileinput_radio.grid(column=0, row=4, sticky=(W, E))
		self.open_input_folder.grid(column=1, row=4, sticky=(E))


		# Positioning a separator
		# self.ver_sep.grid(column=4, row=1, rowspan=8, sticky=(E, W, N, S), padx=(10, 10))
		# self.hor_sep.grid(column=3, row=2, columnspan=28, sticky=(E, W, N, S), pady=(3, 6), padx=(10, 5))
		self.hor_sep2.grid(column=1, row=9, columnspan=30, sticky=(E, W, N, S), pady=(6, 3))


		# Binding functions to combo boxes
		self.combo_region.bind('<<ComboboxSelected>>', self.region_change, self.combo_region)

		self.combo_tables.bind('<<ComboboxSelected>>', self.table_change, self.combo_tables)
		self.waq_combo_tables.bind('<<ComboboxSelected>>', self.waq_table_change)


root = Tk()
app = Application(master=root)
app.mainloop()



        