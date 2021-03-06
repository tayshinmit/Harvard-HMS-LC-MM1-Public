#!/usr/bin/env python
import numpy as np
import shutil
import sys
import cv2
import os


def print_image_info( image, name = 'Image:' ):
    print '-- ', name
    print image

    print 'Shape = ', image.shape
    print 'Size = ', image.size
    print 'Data type = ', image.dtype
    print 'Max value =', np.amax( image )
    print 'Mean = ', np.mean( image )
    print 'Std dev = ', np.std( image )
    print 'Frequency = '
    unique, counts = np.unique( image, return_counts = True )
    print np.asarray((unique, counts)).T
    print
    return


def read_structures_file( path_to_scan, structure ):
    structures_path = path_to_scan + '/structures.dat'
    structures_file = open( structures_path )
    structures = structures_file.readline()
    structures = structures.split('|')
    organ_numbers = []
    for x in range( len(structures) ):
        if structure in structures[x].lower():
            organ_numbers.append( x + 1 )

    return organ_numbers


def read_tags( path_to_scan, file_name, print_values = False ):
    file_path = path_to_scan + '/auxiliary/' + file_name.lstrip('0') + '.dat'
    pixel_spacing = '(0028.0030)'
    image_position = '(0020.0032)'
    aux_file = open(file_path)
    for line in aux_file:
        line_values = line.split(",")
        if line_values[0] == pixel_spacing:
            spacing = { 'dx': float(line_values[1]), 'dy': float(line_values[2]) }
        if line_values[0] == image_position:
            position = { 'x0': int(float(line_values[1])), 'y0': int(float(line_values[2])), 'z0': int(float(line_values[3])) }
    if( print_values ):
        print 'x0 = ', position['x0']
        print 'y0 = ', position['y0']
        print 'z0 = ', position['z0']
        print 'dx = ', spacing['dx']
        print 'dx = ', spacing['dy']
    # The return
    return position, spacing


def convert_to_pixels( contour, position, spacing ):
    # 0 = x points  1 = y points
    contour[:,0] = -100 + (contour[:,0] - position['x0']) / spacing['dx']
    contour[:,1] = -100 + (contour[:,1] - position['y0']) / spacing['dy']
    return contour


def convert_to_mm( contour, position, spacing ):
    contour[:,0] = ((100 + contour[:,0]) * spacing['dx']) + position['x0']
    contour[:,1] = ((100 + contour[:,1]) * spacing['dy']) + position['y0']
    return contour


def read_contour( path_to_files, file_name, tumor_number, contours ):
    # Load contour file
    contour_file = open( path_to_files + '/contours/' + file_name.lstrip('0') + '.' + str(tumor_number) + '.dat' )
    for line in contour_file:
        line = line.split(',')
#        contour = np.loadtxt( line, delimiter="," )
        contour = np.array( line, dtype=np.float32)
        contour = np.reshape( contour, (-1,3) )

        # Delete 3rd column
        contour = np.delete( contour, 2, 1 )

        # Read important information about the image
        position, spacing = read_tags( path_to_files, file_name )

        # Contour data is given in mm => converto to pixels
        contour = convert_to_pixels(contour, position, spacing)

        # Result is still in float point we must convert to unsigned => pixel position
        rounded_contour = np.rint(contour).astype( np.uint )
        contours.append( rounded_contour )
    return contours


def show_contours( img, contours, show_gt = False ):
    if( show_gt ):
        gtruth = np.zeros( img.shape, np.uint8 );
        for contour in contours:
            cv2.drawContours(gtruth, [contour], 0, 255, -1)
        cv2.imshow('ground truth', gtruth)

    rgb_image = cv2.cvtColor( img, cv2.COLOR_GRAY2RGB )
    cv2.drawContours( rgb_image, contours, -1, (0,255,0), 1 )
    cv2.imshow('image', rgb_image)

    cv2.waitKey(0)
    return


def save_gt( path_to_files, file_name, contours ):
    # Load image in grayscale
    # Image values range = [0, 65535]
    # 65535 = 2 bytes => 2^16 -1
    img = cv2.imread( path_to_files + '/pngs/' + file_name + '.png', cv2.IMREAD_GRAYSCALE )

    gtruth = np.zeros( img.shape, np.uint8 );

    for contour in contours:
        cv2.drawContours(gtruth, [contour], 0, 1, -1)

#    line, col = gtruth.shape
#    gtruth = gtruth.reshape(line, col, 1);

    cv2.imwrite( path_to_files + '/ground_truth/' + file_name + '.png' , gtruth)
    return


def generate_gt( root_path, files_type ):
    all_scans_ids = os.listdir( root_path + files_type )
    for scan_id in all_scans_ids:
        path_to_files = root_path + files_type + '/' + scan_id
        print path_to_files
        # content in path_to_files:
        # auxiliary/
        # contours/
        # ground_truth/ -> is going to be created
        # pngs/
        # structures.dat

        tumor_numbers = read_structures_file( path_to_files, 'radiomics_gtv' )

        directory = path_to_files + '/ground_truth/'
        if os.path.exists( directory ):
            shutil.rmtree( directory )
        os.makedirs( directory )

        images_files = os.listdir( path_to_files + '/pngs/' )
        for image_name in images_files:
            # Remove .png
            image_name = image_name.split('.')
            image_name = image_name[0]

            contours = []
            for tumor_number in tumor_numbers:
                file_path = path_to_files + '/contours/' + image_name.lstrip('0') + '.' + str(tumor_number) + '.dat'
                if os.path.exists( file_path ):
                    contours = read_contour( path_to_files, image_name, str(tumor_number), contours )

            save_gt( path_to_files, image_name, contours )
    return


def generate_bb( root_path, text_file_name = 'result.csv' ):
    text_file = open( text_file_name, 'w' )

    scans = os.listdir( root_path )
    for scan_id in scans:
        print scan_id
        path_to_images = root_path + scan_id + '/results/'

        if os.path.exists( path_to_images ):
            images_files = os.listdir( path_to_images )
            for image_name in images_files:
                # Remove .png
                slice_id = image_name.split('.')[0]

                path_to_img = path_to_images + image_name

                image = cv2.imread( path_to_img, cv2.IMREAD_GRAYSCALE )
                # image *= 255

                ret, thresh = cv2.threshold( image, 127, 255, 0 )
                image2, contours, hierarchy = cv2.findContours(thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

                position, spacing = read_tags( root_path + scan_id, slice_id )

                # Contours is a list of numpy arrays
                # len(contours) give the number of tumors
                # The i-th numpy array has len(contours[i]) points (x,y)
                for contour in contours:
                    msg = scan_id + ',' + slice_id.lstrip('0')
                    for points in contour:
                        x = (100 + points[0][0]) * spacing['dx'] + position['x0']
                        y = (100 + points[0][1]) * spacing['dy'] + position['y0']
                        msg += ',' + str(x) + ',' + str(y)
                    msg = msg + '\n'
                    text_file.write( msg )
    return


def generate_bb_from_file( path_to_file, output_file_name = 'result.csv' ):
    with open( path_to_file, 'r') as images_file:
        images_file_lines = images_file.readlines()

    output_file = open( output_file_name, 'w')
    for line in images_file_lines:
        line = line[:-1]
        line = line.split(' ')[1]
        line = line.split('/')

        path_to_scan = line[:-2]
        scan_id = path_to_scan[-1]
        path_to_scan = '/'.join( path_to_scan )

        path_to_image = path_to_scan + '/results/' + line[-1]

        slice_id = line[-1]
        slice_id = slice_id.split('.')[0]

        image = cv2.imread( path_to_image, cv2.IMREAD_GRAYSCALE )
        ret, thresh = cv2.threshold( image, 127, 255, 0 )
        image2, contours, hierarchy = cv2.findContours(thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

        position, spacing = read_tags( path_to_scan, slice_id )
        # Contours is a list of numpy arrays
        # len(contours) give the number of tumors
        # The i-th numpy array has len(contours[i]) points (x,y)
        for contour in contours:
            msg = scan_id + ',' + slice_id.lstrip('0')
            for points in contour:
                x = (100 + points[0][0]) * spacing['dx'] + position['x0']
                y = (100 + points[0][1]) * spacing['dy'] + position['y0']
                msg += ',' + str(x) + ',' + str(y)
            msg = msg + '\n'
            output_file.write( msg )

    output_file.close()
    return


def show_gt( scan_path ):
    print scan_path
    # content in scan_path:
    # auxiliary/
    # contours/
    # ground_truth/ -> is going to be created
    # pngs/
    # structures.dat

    tumor_numbers = read_structures_file( scan_path, 'radiomics_gtv' )

    directory = scan_path + '/ground_truth/'
    if not os.path.exists( directory ):
        print "Error. ground_truth directory doesn't exist !!!"
        sys.exit()

    images_files = os.listdir( scan_path + '/pngs/' )
    for image_name in images_files:
        image_path = scan_path + '/pngs/' + image_name
        print image_path

        # Remove .png
        image_name = image_name.split('.')
        image_name = image_name[0]

        contours = []
        for tumor_number in tumor_numbers:
            file_path = scan_path + '/contours/' + image_name.lstrip('0') + '.' + str(tumor_number) + '.dat'
            if os.path.exists( file_path ):
                contours = read_contour( scan_path, image_name, str(tumor_number), contours )

        image = cv2.imread( image_path, cv2.IMREAD_GRAYSCALE )
        show_contours( image, contours, True )
    return


def lung_gt( root_path ):
    scans = os.listdir( root_path )
    for scan_id in scans:
        scan_path = root_path + scan_id
        print scan_path

        gt_directory = scan_path + '/lung_gt/'
        if not os.path.exists( gt_directory ):
            os.makedirs( gt_directory )

        tumor_numbers = read_structures_file( scan_path, 'radiomics_gtv' )
        lung_numbers = read_structures_file( scan_path, 'lung' )
#            heart_numbers = read_structures_file( scan_path, 'heart' )

        images_files = os.listdir( scan_path + '/pngs/' )
        for image_name in images_files:
            image_path = scan_path + '/pngs/' + image_name
            # Remove .png
            image_name = image_name.split('.')
            image_name = image_name[0]

            tumor_contours = []
            for tumor_number in tumor_numbers:
                file_path = scan_path + '/contours/' + image_name.lstrip('0') + '.' + str(tumor_number) + '.dat'
                if os.path.exists( file_path ):
                    tumor_contours = read_contour( scan_path, image_name, str(tumor_number), tumor_contours )

            lung_contours = []
            for lung_number in lung_numbers:
                file_path = scan_path + '/contours/' + image_name + '.' + str(lung_number) + '.dat'
                if os.path.exists( file_path ):
                    lung_contours = read_contour( scan_path, image_name, str(lung_number), lung_contours )

#                heart_contours = []
#                for heart_number in heart_numbers:
#                    file_path = scan_path + '/contours/' + image_name + '.' + str(heart_number) + '.dat'
#                    if os.path.exists( file_path ):
#                        heart_contours = read_contour( scan_path, image_name, str(heart_number), heart_contours )

            image = cv2.imread( image_path, cv2.IMREAD_GRAYSCALE )

            gtruth = np.zeros( image.shape, np.uint8 );
#                gtruth = cv2.cvtColor( gtruth, cv2.COLOR_GRAY2RGB )
            for contour in lung_contours:
                cv2.drawContours(gtruth, [contour], 0, 1, -1)
            for contour in tumor_contours:
                cv2.drawContours(gtruth, [contour], 0, 2, -1)

            cv2.imwrite( gt_directory + image_name + '.png', gtruth )

#                gtruth = cv2.cvtColor( gtruth, cv2.COLOR_GRAY2RGB )
#                for contour in heart_contours:
#                    cv2.drawContours(gtruth, [contour], 0, (255, 0, 0), -1)
#                for contour in lung_contours:
#                    cv2.drawContours(gtruth, [contour], 0, (0, 255, 0), -1)
#                for contour in tumor_contours:
#                    cv2.drawContours(gtruth, [contour], 0, (0, 0, 255), -1)
#                cv2.imshow('ground truth', gtruth)

#                # The order is important -> last override first
#                rgb_image = cv2.cvtColor( image, cv2.COLOR_GRAY2RGB )
#                cv2.drawContours( rgb_image, heart_contours, -1, (255, 0, 0), 1 )
#                cv2.drawContours( rgb_image, lung_contours, -1, (0, 255, 0), 1 )
#                cv2.drawContours( rgb_image, tumor_contours, -1, (0, 0, 255), 1 )
#                cv2.imshow('image', rgb_image)

#                cv2.waitKey(0)
    return


def save_lung_gt_paths( root_path, file_type ):
    text_file_name = file_type + '_lung_gt.txt'
    mix_text_file_name = file_type + '_lung_gt_mix.txt'

    # All images where the scan has lung contours
    text_file = open( text_file_name, 'w' )
    # All tumor images, 1/3 of all lung images and 1/10 of images without lung and cancer cells
    mix_text_file = open( mix_text_file_name, 'w' )

    scans = os.listdir( root_path )
    for scan_id in scans:
        scan_path = root_path + scan_id
        print scan_path

        lung_numbers = read_structures_file( scan_path, 'lung' )
        tumor_numbers = read_structures_file( scan_path, 'radiomics_gtv' )

        if( lung_numbers ):
            images_files = os.listdir( scan_path + '/lung_gt/' )
            for image_name in images_files:
                # Remove .png
                image_name = image_name.split('.')
                image_name = image_name[0]

                msg = root_path + scan_id + '/pngs/' + image_name + '.png'
                msg = msg + ' '
                msg = msg + root_path + scan_id + '/lung_gt/' + image_name + '.png'
                msg = msg + '\n'

                text_file.write( msg )

                tumor_contours = []
                for tumor_number in tumor_numbers:
                    file_path = scan_path + '/contours/' + image_name.lstrip('0') + '.' + str(tumor_number) + '.dat'
                    if os.path.exists( file_path ):
                        tumor_contours = read_contour( scan_path, image_name, str(tumor_number), tumor_contours )

                lung_contours = []
                for lung_number in lung_numbers:
                    file_path = scan_path + '/contours/' + image_name + '.' + str(lung_number) + '.dat'
                    if os.path.exists( file_path ):
                        lung_contours = read_contour( scan_path, image_name, str(lung_number), lung_contours )

                if( tumor_contours ):
                    msg = root_path + scan_id + '/pngs/' + image_name + '.png'
                    msg = msg + ' '
                    msg = msg + root_path + scan_id + '/lung_gt/' + image_name + '.png'
                    msg = msg + '\n'
                    mix_text_file.write( msg )
                elif( lung_contours ):
                    if( np.random.randint(3, size=1) == 1 ):
                        msg = root_path + scan_id + '/pngs/' + image_name + '.png'
                        msg = msg + ' '
                        msg = msg + root_path + scan_id + '/lung_gt/' + image_name + '.png'
                        msg = msg + '\n'
                        mix_text_file.write( msg )
                elif( np.random.randint(10, size=1) == 5 ):
                    msg = root_path + scan_id + '/pngs/' + image_name + '.png'
                    msg = msg + ' '
                    msg = msg + root_path + scan_id + '/lung_gt/' + image_name + '.png'
                    msg = msg + '\n'
                    mix_text_file.write( msg )
    return


def calculate_class_weighting_using_dir( scan_path ):
    normal_cells = 0.0
    cancer_cells = 0.0

    scan_ids = os.listdir( scan_path )
    for scan_id in scan_ids:
        print scan_path + scan_id

        gt_directory = scan_path + scan_id + '/ground_truth/'
        if not os.path.exists( gt_directory ):
            print "Error. ground_truth directory doesn't exist !!!"
            sys.exit()

        gts = os.listdir( gt_directory )
        for gt_name in gts:
            ground_truth = cv2.imread( gt_directory + gt_name, cv2.IMREAD_GRAYSCALE )
            unique, counts = np.unique( ground_truth, return_counts = True )
#                print unique
#                print 'Zeros = ', counts[0]
#                if len( counts ) == 2:
#                    print '255s = ', counts[1]
#                print

            normal_cells += counts[0]
            if len( counts ) == 2:
                cancer_cells += counts[1]

    print 'Number of normal cells pixels = ', normal_cells
    print 'Number of cancer cells pixels = ', cancer_cells
    mean = (normal_cells + cancer_cells)/ 2.0
    print 'Mean = ', mean
    print 'Normal cells weight = ', mean / normal_cells
    print 'Cancer cells weight = ', mean / cancer_cells

    return


def calculate_class_weighting( path_to_file ):
    normal_cells = 0.0
    cancer_cells = 0.0
    lung_cells = 0.0

    training_file = open( path_to_file )
    gt_files = training_file.readlines()

    for gt_file in gt_files:
        ground_truth_dir = gt_file.split(' ')[1]
        ground_truth_dir = ground_truth_dir[:-1]

        ground_truth = cv2.imread( ground_truth_dir, cv2.IMREAD_GRAYSCALE )
        unique, counts = np.unique( ground_truth, return_counts = True )
#            print unique
#            print 'Zeros = ', counts[0]
#            if len( counts ) == 2:
#                print '255s = ', counts[1]
#            print

        normal_cells += counts[0]

        if len( counts ) == 2:
            lung_cells += counts[1]

        if len( counts ) == 3:
            lung_cells += counts[1]
            cancer_cells += counts[2]

    print 'Number of lung cells pixels = ', lung_cells
    print 'Number of cancer cells pixels = ', cancer_cells
    print 'Number of normal cells pixels = ', normal_cells

    mean = 0.0
    if lung_cells != 0:
        mean = lung_cells
        print 'Mean = ', mean
        print 'Lung cells weight = ', 1
    else:
        mean = (normal_cells + cancer_cells)/ 2.0
        print 'Mean = ', mean

    print 'Normal cells weight = ', mean / normal_cells
    print 'Cancer cells weight = ', mean / cancer_cells

    return


def compute_images_mean( root_path ):
    images_mean = []

    scan_paths = [root_path + '/train/', root_path + '/test/']
    for scan_path in scan_paths:
        scan_ids = os.listdir( scan_path )
        for scan_id in scan_ids:
            print scan_path + scan_id

            subdirs = ['/pngs/', '/flipped/pngs/', '/rotated/pngs/']
            for subdir in subdirs:
                pngs_directory = scan_path + scan_id + subdir

                images = os.listdir( pngs_directory )
                mean = 0.0
                for image_name in images:
                    path_to_img = pngs_directory + image_name
                    image = cv2.imread( path_to_img, cv2.IMREAD_GRAYSCALE )
                    mean += np.mean( image )

                images_mean.append( mean / float( len(images) ) )

    print len( images_mean )
    image_mean = sum( images_mean ) / float( len( images_mean ) )

    print 'Image mean = ', image_mean
    return



