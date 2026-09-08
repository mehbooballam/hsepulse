import unittest
from unittest.mock import Mock, patch
import google_connection as gc

class LinkConnectionTests(unittest.TestCase):
 def test_link_validation(self):
  self.assertEqual(gc.spreadsheet_id('https://docs.google.com/spreadsheets/d/abc_123-X/edit?usp=sharing#gid=0'),'abc_123-X')
  for link in ['https://evil.example/spreadsheets/d/abc/edit','https://docs.google.com.evil.example/spreadsheets/d/abc/edit','http://docs.google.com/spreadsheets/d/abc/edit','https://docs.google.com/spreadsheets/d/e/published/pubhtml','abc']:
   with self.assertRaises(ValueError): gc.spreadsheet_id(link)
 def test_denied_editor_keeps_existing_connection(self):
  accounts=Mock(); book=Mock(); book.batch_update.side_effect=PermissionError('read only')
  with patch.object(gc,'require_admin'),patch.object(gc,'sheet_client') as factory,patch.object(gc,'initialize') as init:
   factory.return_value.open_by_key.return_value=book
   with self.assertRaises(PermissionError): gc.choose(accounts,{}, {},'https://docs.google.com/spreadsheets/d/abc/edit')
   init.assert_not_called(); accounts.mutate.assert_not_called()
 def test_non_admin_cannot_contact_google(self):
  with patch.object(gc,'require_admin',side_effect=gc.AccessDenied('denied')),patch.object(gc,'sheet_client') as factory:
   with self.assertRaises(gc.AccessDenied): gc.choose(Mock(),{}, {},'https://docs.google.com/spreadsheets/d/abc/edit')
   factory.assert_not_called()
if __name__=='__main__': unittest.main()
