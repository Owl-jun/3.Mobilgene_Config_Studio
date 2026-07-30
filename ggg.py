#region INCLUDES
from lxml import etree
import os
import json
import copy
import streamlit as st
#endregion

#region FOR_DEBUG_TREE
# Recursively prints the parsed info structure in a readable tree format.
def print_info( info, indent = '', visited = None, file = None ):
  if visited is None:
    visited = set()

  if isinstance( info, (dict, list) ):
    info_id = id( info )
    if info_id in visited:
      print( '{}<already visited: {} (id={})>'.format( indent, type( info ).__name__, info_id ), file = file )
      return
    visited.add( info_id )

  if isinstance( info, dict ):
    if 'ref' in info and 'val' in info:
      ref = info['ref']
      if ref is None:
        print( '{}ref : None'.format( indent ), file = file )
      else:
        print( '{}ref : {} (id={})'.format( indent, type( ref ).__name__, id( ref ) ), file = file )

      val = info['val']
      if isinstance( val, (dict, list) ):
        print( '{}val :'.format( indent ), file = file )
        print_info( val, indent + '  ', visited, file )
      else:
        print( '{}val : {!r}'.format( indent, val ), file = file )
    else:
      for key, value in info.items():
        print( '{}{}'.format( indent, key ), file = file )
        print_info( value, indent + '  ', visited, file )
  elif isinstance( info, list ):
    for index, value in enumerate( info ):
      print( '{}[{}]'.format( indent, index ), file = file )
      print_info( value, indent + '  ', visited, file )
  else:
    print( '{}{!r}'.format( indent, info ), file = file )


# Writes one or more parsed info trees to a UTF-8 text log file.
def save_info_log( path_log, list_info ):
  with open( path_log, 'w', encoding = 'utf-8' ) as file_log:
    for index, info_log in enumerate( list_info ):
      if index > 0:
        print( file = file_log )
      print( '===== {} ====='.format( info_log['name'] ), file = file_log )
      print_info( info_log['info'], file = file_log )

#endregion

#region BACK_FUNCTIONS

#region ARXML_Short_Name_Path()
class ARXML_Short_Name_Path():
  def __init__( self, short_name, elmt ):
    self.short_name = short_name
    self.elmt = elmt
    self.children = []
    self.parent = None

  def __iadd__( self, child ):
    if isinstance( child, ARXML_Short_Name_Path ):
      self.children.append( child )
      child.parent = self
      return self
    return NotImplemented

  # def repr_with_children( self, indent = '' ):
  #   str_repr = indent + '- ' + self.short_name
  #   if self.children:
  #     str_repr += '\n' + '\n'.join( child.repr_with_children( indent + '  ' ) for child in self.children )
  #   return str_repr

  # def __repr__( self ):
  #   return self.repr_with_children()

  def absolute_path( self ):
    if self.parent == None:
      return '/' + self.short_name
    else:
      return self.parent.absolute_path() + '/' + self.short_name

  def find( self, str_short_name_path ):
    list_short_name = str_short_name_path.split( '/', 1 )
    if not list_short_name[0]:
      list_short_name = list_short_name[1].split( '/', 1 )

    if self.short_name == list_short_name[0]:
      list_short_name.pop( 0 )
      if list_short_name:
        for child in self.children:
          short_name_path = child.find( list_short_name[0] )
          if short_name_path:
            return short_name_path #child.find( list_short_name[0] )
      else:
        return self
    return None
#endregion

#region ARXML_ELMT()
class ARXML_ELMT():
  def __init__( self, elmt: etree._Element, ns: dict, info, short_name_path_parent ):
    self.elmt = elmt
    self.ns = ns
    self.info = info

    self.elmts_sub = []
    self.elmts_cntr = []
    self.elmts_sub_cntr = []
    self.elmts_param = []
    self.elmts_ref = []
    self.elmts_temp = []

    self.short_name_path_parent = short_name_path_parent
    self.short_name_path = None
    self.str_desc_ref = None

    self.to_info()

  def to_info( self ):
    if self.elmt.text:
      self.info["#text"] = self.elmt.text.strip()

    if self.elmt.attrib:
      self.info["@attributes"] = self.elmt.attrib

    str_tag = self.elmt.tag.replace( f'{{{self.ns[None]}}}', '' )
    if str_tag == 'CONTAINERS':
      elmts_child = self.elmts_cntr
    elif str_tag == 'SUB-CONTAINERS':
      elmts_child = self.elmts_sub_cntr
    elif str_tag == 'PARAMETERS':
      elmts_child = self.elmts_param
    elif str_tag == 'REFERENCES':
      elmts_child = self.elmts_ref
    else:
      elmts_child = self.elmts_temp

    short_name_path = self.short_name_path_parent
    child_short_name = self.elmt.find( 'SHORT-NAME', self.ns )
    if child_short_name is not None:
      self.short_name_path = ARXML_Short_Name_Path( child_short_name.text, self )
      if self.short_name_path_parent is not None:
        self.short_name_path_parent += self.short_name_path
      short_name_path = self.short_name_path

    child_def_ref = self.elmt.find( 'DEFINITION-REF', self.ns )
    if child_def_ref is not None:
      self.str_desc_ref = child_def_ref.text

    children = list( self.elmt )
    for child in children:
      if child.tag is etree.Comment:
        continue

      info_child = {}
      elmt_child = ARXML_ELMT( child, self.ns, info_child, short_name_path )
      self.elmts_sub.append( elmt_child )
      elmts_child.append( elmt_child )

      str_tag = child.tag.replace( f'{{{self.ns[None]}}}', '' )
      if str_tag not in self.info:
        self.info[str_tag] = info_child
      else:
        if not isinstance( self.info[str_tag], list ):
          self.info[str_tag] = [ self.info[str_tag] ]
        self.info[str_tag].append( info_child )

  def find_short_name_path_root( self ):
    if self.short_name_path is not None:
      return self.short_name_path
    else:
      for elmt_sub in self.elmts_sub:
        short_name_path = elmt_sub.find_short_name_path_root()
        if short_name_path is not None:
          return short_name_path
    return None
#endregion

#region ARXML_DOC()
class ARXML_DOC():
  # Loads an ARXML document and builds its recursive element information tree.
  def __init__( self, path ):
    self.doc = etree.parse( path )  # get file and convert to tree
    self.elmt_root = self.doc.getroot() # get root xml tag -> output e. g. {http://autosar.org/schema/r4.0}AUTOSAR
    self.ns = self.elmt_root.nsmap  # save {namespace(ns)} info
    self.info = dict()

    self.root = ARXML_ELMT( self.elmt_root, self.ns, self.info, None )
    self.short_name_path_root = self.root.find_short_name_path_root()
    # print( json.dumps( self.info, indent = 2 ) )
    # print( self.info )
#endregion

# Returns the SHORT-NAME value stored in an ARXML element wrapper.
def get_arxml_elmt_short_name( arxml_elmt ):
  if arxml_elmt.short_name_path is None:
    return None
  return arxml_elmt.short_name_path.short_name


# Returns a simple val field for the requested info key.
def get_arxml_elmt_info_value( arxml_elmt, key ):
  if key == 'SHORT-NAME':
    return get_arxml_elmt_short_name( arxml_elmt )
  if key == 'DEFINITION-REF':
    return arxml_elmt.str_desc_ref

  elmt_value = arxml_elmt.elmt.find( key, arxml_elmt.ns )
  if elmt_value is None:
    return None
  return elmt_value.text


# Yields all child parser objects referenced by the current info node.
def iter_arxml_elmt_children( arxml_elmt ):
  yield from arxml_elmt.elmts_sub


# Checks whether the wrapped XML element is an ECU configuration module.
def is_arxml_module_configuration( arxml_elmt ):
  return etree.QName( arxml_elmt.elmt ).localname == 'ECUC-MODULE-CONFIGURATION-VALUES'

# Recursively finds an ARXML element by its absolute SHORT-NAME path.
def find_arxml_elmt_by_short_name_path( arxml_elmt, short_name_path, parent_path = '' ):
  short_name = get_arxml_elmt_short_name( arxml_elmt )
  current_path = parent_path

  if short_name is not None:
    current_path += '/' + short_name
    if current_path == short_name_path:
      return arxml_elmt

  for child in iter_arxml_elmt_children( arxml_elmt ):
    elmt_found = find_arxml_elmt_by_short_name_path( child, short_name_path, current_path )
    if elmt_found is not None:
      return elmt_found

  return None

# Returns numeric constraints declared by the matching parameter definition.
def get_dcm_number_limits( arxml_doc_spec, definition_ref, parameter_type ):
  arxml_elmt_spec = find_arxml_elmt_by_short_name_path( arxml_doc_spec.root, definition_ref )
  if arxml_elmt_spec is None:
    return None, None

  converter = int if parameter_type == 'integer' else float
  values = []
  for tag in [ 'MIN', 'MAX' ]:
    elmt_value = arxml_elmt_spec.elmt.find( tag, arxml_elmt_spec.ns )
    try:
      values.append( converter( elmt_value.text, 0 ) if parameter_type == 'integer' else converter( elmt_value.text ) )
    except ( AttributeError, TypeError, ValueError ):
      values.append( None )
  return values[0], values[1]
#endregion BACK_FUNCTIONS

#region FRONT_FUNCTIONS
# Stores the selected configuration element in the Streamlit session state.
def on_arxml_elmt_selected( arxml_elmt ):
  st.session_state.arxml_elmt_selected = arxml_elmt

# Resolves and displays the Spec definition referenced by a configuration element.
def st_display_arxml_elmt_spec( arxml_doc_spec, arxml_elmt_cfg ):
  definition_ref = get_arxml_elmt_info_value( arxml_elmt_cfg, 'DEFINITION-REF' )
  if definition_ref is None:
    with st.expander( 'None - PARAMETER-VALUES' ):
      st.info( '선택된 항목에 DEFINITION-REF가 없습니다.' )
    return

  arxml_elmt_spec = find_arxml_elmt_by_short_name_path( arxml_doc_spec.root, definition_ref )
  if arxml_elmt_spec is None:
    with st.expander( definition_ref + ' - PARAMETER-VALUES', expanded = True ):
      st.warning( 'Spec에서 DEFINITION-REF를 찾을 수 없습니다: {}'.format( definition_ref ) )
    return

  if is_arxml_module_configuration( arxml_elmt_cfg ):
    with st.expander( 'DEFINITION-REF : ' + definition_ref ):
      elmt_desc = arxml_elmt_spec.elmt.find( 'DESC/L-2', arxml_elmt_spec.ns )
      if elmt_desc is None:
        st.info( 'Spec에 DESC 정보가 없습니다.' )
      else:
        st.write( ''.join( elmt_desc.itertext() ).strip() )
    return

  with st.expander( 'DEFINITION-REF : ' + definition_ref, expanded = False ):
    elmt_disp = copy.deepcopy( arxml_elmt_spec.elmt )
    elmt_sub = elmt_disp.find( 'SUB-CONTAINERS', arxml_elmt_spec.ns )
    if elmt_sub is not None:
      elmt_disp.remove( elmt_sub )
    etree.indent( elmt_disp, space = '  ' )
    st.code( etree.tostring( elmt_disp, encoding = 'unicode' ), language = 'xml' )


# Converts an AUTOSAR parameter VALUE into the Python type used by its widget.
def parse_dcm_parameter_value( value_text, parameter_type ):
  if parameter_type == 'boolean':
    return value_text.strip().lower() in [ '1', 'true' ]
  if parameter_type == 'integer':
    return int( value_text, 0 )
  if parameter_type == 'float':
    return float( value_text )
  return value_text


# Keeps the source ARXML's boolean and hexadecimal notation when an editor value changes.
def format_dcm_parameter_value( value, parameter_type, original_text ):
  if parameter_type == 'boolean':
    if original_text.strip().lower() in [ 'true', 'false' ]:
      return 'true' if bool( value ) else 'false'
    return '1' if bool( value ) else '0'
  if parameter_type == 'integer':
    if original_text.strip().lower().startswith( '0x' ):
      return '0x{:X}'.format( int( value ) )
    return str( int( value ) )
  if parameter_type == 'float':
    return str( float( value ) )
  return str( value )


# Renders DCM parameter values with one widget selected from each AUTOSAR type.
def st_display_dcm_parameter_editor( arxml_doc_spec, arxml_elmt_cfg ):
  definition_ref = get_arxml_elmt_info_value( arxml_elmt_cfg, 'DEFINITION-REF' )
  if definition_ref is None or not definition_ref.startswith( '/AUTRON/Dcm/' ):
    with st.expander( 'Not Available - PARAMETER-VALUES' ):
      st.info( '컨테이너를 선택하면 파라미터 편집기가 표시됩니다.' )
    return

  elmt_parameter_values = arxml_elmt_cfg.elmt.find( 'PARAMETER-VALUES', arxml_elmt_cfg.ns )
  if elmt_parameter_values is None:
    with st.expander( definition_ref + ' - PARAMETER-VALUES' ):
      st.info( '선택한 컨테이너에 파라미터 값이 없습니다.' )
    return

  parameter_values = {}
  widget_config = {}
  parameter_by_widget = {}
  parameter_definition_by_widget = {}
  parameter_definition_refs = set()

  for elmt_parameter in elmt_parameter_values:
    elmt_definition_ref = elmt_parameter.find( 'DEFINITION-REF', arxml_elmt_cfg.ns )
    elmt_value = elmt_parameter.find( 'VALUE', arxml_elmt_cfg.ns )
    if elmt_definition_ref is None or elmt_value is None or elmt_value.text is None:
      continue

    parameter_definition_ref = elmt_definition_ref.text
    parameter_name = parameter_definition_ref.rsplit( '/', 1 )[-1]
    destination = elmt_definition_ref.get( 'DEST', '' )
    parameter_definition_refs.add( parameter_definition_ref )

    if destination == 'ECUC-BOOLEAN-PARAM-DEF':
      parameter_type = 'boolean'
    elif destination == 'ECUC-INTEGER-PARAM-DEF':
      parameter_type = 'integer'
    elif destination == 'ECUC-FLOAT-PARAM-DEF':
      parameter_type = 'float'
    elif destination == 'ECUC-FUNCTION-NAME-DEF':
      parameter_type = 'function'
    else:
      continue

    widget_name = parameter_name
    suffix = 2
    while widget_name in parameter_values:
      widget_name = '{} ({})'.format( parameter_name, suffix )
      suffix += 1

    try:
      parameter_values[widget_name] = parse_dcm_parameter_value( elmt_value.text, parameter_type )
    except ValueError:
      continue

    arxml_elmt_spec = find_arxml_elmt_by_short_name_path( arxml_doc_spec.root, parameter_definition_ref )
    help_text = None
    if arxml_elmt_spec is not None:
      elmt_desc = arxml_elmt_spec.elmt.find( 'DESC/L-2', arxml_elmt_spec.ns )
      if elmt_desc is not None:
        help_text = ''.join( elmt_desc.itertext() ).strip()

    if parameter_type == 'boolean':
      widget_config[widget_name] = {
        'label': parameter_name,
        'help': help_text,
      }
    elif parameter_type == 'function':
      widget_config[widget_name] = {
        'label': parameter_name,
        'help': help_text,
      }
    else:
      min_value, max_value = get_dcm_number_limits(
        arxml_doc_spec,
        parameter_definition_ref,
        parameter_type,
      )
      widget_config[widget_name] = {
        'label': parameter_name,
        'help': help_text,
        'min_value': min_value,
        'max_value': max_value,
        'step': 1 if parameter_type == 'integer' else None,
        'format': '%d' if parameter_type == 'integer' else None,
      }

    parameter_by_widget[widget_name] = ( elmt_value, parameter_type, elmt_value.text )

  arxml_elmt_spec = find_arxml_elmt_by_short_name_path( arxml_doc_spec.root, definition_ref )
  if arxml_elmt_spec is not None:
    elmt_parameters = arxml_elmt_spec.elmt.find( 'PARAMETERS', arxml_elmt_spec.ns )
    if elmt_parameters is not None:
      for elmt_function in elmt_parameters.findall( 'ECUC-FUNCTION-NAME-DEF', arxml_elmt_spec.ns ):
        elmt_short_name = elmt_function.find( 'SHORT-NAME', arxml_elmt_spec.ns )
        if elmt_short_name is None:
          continue

        parameter_name = elmt_short_name.text
        parameter_definition_ref = definition_ref + '/' + parameter_name
        if parameter_definition_ref in parameter_definition_refs:
          continue

        widget_name = parameter_name
        suffix = 2
        while widget_name in parameter_values:
          widget_name = '{} ({})'.format( parameter_name, suffix )
          suffix += 1

        elmt_desc = elmt_function.find( 'DESC/L-2', arxml_elmt_spec.ns )
        help_text = None
        if elmt_desc is not None:
          help_text = ''.join( elmt_desc.itertext() ).strip()

        parameter_values[widget_name] = ''
        widget_config[widget_name] = {
          'label': parameter_name,
          'help': help_text,
        }
        parameter_by_widget[widget_name] = ( None, 'function', '' )
        parameter_definition_by_widget[widget_name] = parameter_definition_ref

  if not parameter_values:
    st.info( definition_ref + ' - 편집 가능한 파라미터가 없습니다.' )
    return

  with st.expander( definition_ref + ' - PARAMETER-VALUES', expanded = True ):
    for widget_name, ( elmt_value, parameter_type, original_text ) in parameter_by_widget.items():
      widget_key = 'dcm_parameter_widget:{}:{}'.format(
        arxml_elmt_cfg.elmt.getroottree().getpath( arxml_elmt_cfg.elmt ),
        widget_name,
      )
      if parameter_type == 'boolean':
        edited_value = st.checkbox(
          widget_config[widget_name]['label'],
          value = parameter_values[widget_name],
          help = widget_config[widget_name]['help'],
          key = widget_key,
        )
      elif parameter_type == 'function':
        edited_value = st.text_input(
          widget_config[widget_name]['label'],
          value = parameter_values[widget_name],
          help = widget_config[widget_name]['help'],
          key = widget_key,
        )
      else:
        edited_value = st.number_input(
          widget_config[widget_name]['label'],
          value = parameter_values[widget_name],
          min_value = widget_config[widget_name]['min_value'],
          max_value = widget_config[widget_name]['max_value'],
          step = widget_config[widget_name]['step'],
          format = widget_config[widget_name]['format'],
          help = widget_config[widget_name]['help'],
          key = widget_key,
        )

      if elmt_value is not None:
        elmt_value.text = format_dcm_parameter_value( edited_value, parameter_type, original_text )
      elif str( edited_value ):
        namespace = '{{{}}}'.format( arxml_elmt_cfg.ns[None] )
        elmt_parameter = etree.SubElement(
          elmt_parameter_values,
          namespace + 'ECUC-TEXTUAL-PARAM-VALUE',
        )
        elmt_definition_ref = etree.SubElement( elmt_parameter, namespace + 'DEFINITION-REF' )
        elmt_definition_ref.set( 'DEST', 'ECUC-FUNCTION-NAME-DEF' )
        elmt_definition_ref.text = parameter_definition_by_widget[widget_name]
        elmt_value = etree.SubElement( elmt_parameter, namespace + 'VALUE' )
        elmt_value.text = str( edited_value )


# Recursively renders all referenced child elements in the current Streamlit container.
def st_display_arxml_elmt_children( arxml_elmt, current_path, display_module_tree ):
  for child in iter_arxml_elmt_children( arxml_elmt ):
    st_display_arxml_elmt_tree( child, current_path, display_module_tree )


# Renders configuration modules and their descendants as nested Streamlit expanders.
def st_display_arxml_elmt_tree( arxml_elmt, parent_path = '', display_module_tree = False ):
  short_name = get_arxml_elmt_short_name( arxml_elmt )

  if short_name is None:
    st_display_arxml_elmt_children( arxml_elmt, parent_path, display_module_tree )
    return

  current_path = parent_path + '/' + short_name
  display_module_tree = display_module_tree or is_arxml_module_configuration( arxml_elmt )

  if display_module_tree:
    if arxml_elmt.short_name_path.children:
      with st.expander(
        short_name,
        type = 'compact',
        key = current_path,
        on_change = on_arxml_elmt_selected,
        args = ( arxml_elmt, )
      ):
        st_display_arxml_elmt_children( arxml_elmt, current_path, display_module_tree )
    else:
      st.button(
        short_name,
        type = 'tertiary',
        key = current_path,
        on_click = on_arxml_elmt_selected,
        args = ( arxml_elmt, )
      )
  else:
    st_display_arxml_elmt_children( arxml_elmt, current_path, display_module_tree )
#endregion FRONT_FUNCTIONS

path_arxml_cfg_spec = 'AUTRON_AUTOSAR_Dcm_ECU_Configuration_PDF.arxml'
path_arxml_cfg = 'Ecud_Dcm.arxml'

if 'arxml_doc_cfg_spec' not in st.session_state:
  st.session_state.arxml_doc_cfg_spec = ARXML_DOC( path_arxml_cfg_spec )
if 'arxml_doc_cfg' not in st.session_state:
  st.session_state.arxml_doc_cfg = ARXML_DOC( path_arxml_cfg )
if 'arxml_elmt_selected' not in st.session_state:
  st.session_state.arxml_elmt_selected = None

#region !<<UNUSE>>! FOR_DEBUG_TREE
# path_info_log = os.path.join( os.path.dirname( os.path.abspath( __file__ ) ), 'arxml_info_log.txt' )
# save_info_log(
#   path_info_log,
#   [
#     { 'name': path_arxml_cfg_spec, 'info': st.session_state.arxml_doc_cfg_spec.info },
#     { 'name': path_arxml_cfg,      'info': st.session_state.arxml_doc_cfg.info      },
#   ]
# )
#endregion

st.markdown(
  """
  <style>
  [data-testid="stVerticalBlock"] {
    gap: 0px !important;
  }

  [data-testid="stElementContainer"] {
    padding-top: 0rem !important;
    padding-bottom: 0rem !important;
    margin-top: 0rem !important;
    margin-bottom: 0rem !important;
  }

  [data-testid="stExpanderDetails"] {
    padding-top: 0rem !important;
    padding-bottom: 0rem !important;
    margin-top: 0rem !important;
    margin-bottom: 0rem !important;
    padding-left: 1rem;
  }

  button[kind="tertiary"] {
    padding-top: 2px !important;
    padding-bottom: 2px !important;
    min-height: unset !important;
  }

  </style>
  """,
  unsafe_allow_html=True
)

st.set_page_config( page_title = 'ARXML(AUTOSAR XML) Editor', layout = 'wide' )

[ view_left, view_right ] = st.columns( [2, 8], width = 'stretch' )

with view_left:
  with st.container( border = True, height = 800 ):
    st_display_arxml_elmt_tree( st.session_state.arxml_doc_cfg.root )

with view_right:
  with st.container( border = True, height = 800 ):
    if st.session_state.arxml_elmt_selected is not None:
      st_display_arxml_elmt_spec( st.session_state.arxml_doc_cfg_spec, st.session_state.arxml_elmt_selected )
      st_display_dcm_parameter_editor( st.session_state.arxml_doc_cfg_spec, st.session_state.arxml_elmt_selected )
    else:
      st.info( '좌측 컨테이너를 선택하세요.' )
